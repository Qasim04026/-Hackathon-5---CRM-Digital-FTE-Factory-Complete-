import os
import json
import asyncio
import logging
from dotenv import load_dotenv
import google.generativeai as genai
import asyncpg
from uuid import UUID
from datetime import datetime

from production.agent.prompts import SYSTEM_PROMPT

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CustomerSuccessAgent:
    def __init__(self):
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY not found in .env file")
        genai.configure(api_key=self.gemini_api_key)

        self.db_url = os.getenv("DATABASE_URL")
        if not self.db_url:
            raise ValueError("DATABASE_URL not found in .env file")
        self.pool = None

        self.tools = [
            {
                "name": "search_knowledge_base",
                "description": "Search the knowledge base for relevant information.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "max_results": {"type": "integer", "default": 5}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "create_ticket",
                "description": "Create a support ticket for an issue that requires further action.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "customer_id": {"type": "string"},
                        "issue": {"type": "string"},
                        "priority": {"type": "string", "enum": ["low", "medium", "high", "urgent"]},
                        "channel": {"type": "string"}
                    },
                    "required": ["customer_id", "issue", "priority", "channel"]
                }
            },
            {
                "name": "get_customer_history",
                "description": "Retrieve past conversations and tickets for a specific customer.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "customer_id": {"type": "string"}
                    },
                    "required": ["customer_id"]
                }
            },
            {
                "name": "escalate_to_human",
                "description": "Escalate the current conversation to a human agent.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "ticket_id": {"type": "string"},
                        "reason": {"type": "string"}
                    },
                    "required": ["ticket_id", "reason"]
                }
            },
            {
                "name": "send_response",
                "description": "Send a message back to the customer through their channel.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "ticket_id": {"type": "string"},
                        "message": {"type": "string"},
                        "channel": {"type": "string"}
                    },
                    "required": ["message", "channel"]
                }
            },
        ]

        self.model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=SYSTEM_PROMPT
        )

    async def _init_db_pool(self):
        if not self.pool:
            try:
                self.pool = await asyncpg.create_pool(self.db_url)
                logger.info("Database pool created successfully.")
            except Exception as e:
                logger.error(f"Failed to create database pool: {e}")
                raise

    async def _execute_db_query(self, query: str, *args, fetch: bool = True, fetchval: bool = False, execute: bool = False):
        await self._init_db_pool()
        async with self.pool.acquire() as conn:
            try:
                if execute:
                    await conn.execute(query, *args)
                    return None
                elif fetchval:
                    return await conn.fetchval(query, *args)
                elif fetch:
                    return await conn.fetch(query, *args)
            except Exception as e:
                logger.error(f"Database query failed: {query} with error: {e}")
                raise

    async def search_knowledge_base(self, query: str, max_results: int = 5):
        logger.info(f"Searching knowledge base for: {query}")
        try:
            results = await self._execute_db_query(
                """SELECT title, content, category 
                   FROM knowledge_base
                   WHERE 
                     content ILIKE $1 OR 
                     title ILIKE $1 OR
                     category ILIKE $2
                   LIMIT $3""",
                f"%{query}%",
                f"%{query}%",
                max_results
            )
            
            if not results:
                words = query.lower().split()
                all_results = []
                for word in words[:3]:
                    if len(word) > 3:
                        word_results = await self._execute_db_query(
                            """SELECT title, content, category 
                               FROM knowledge_base
                               WHERE content ILIKE $1 OR title ILIKE $1
                               LIMIT $2""",
                            f"%{word}%",
                            max_results
                        )
                        all_results.extend(word_results)
                
                seen = set()
                results = []
                for r in all_results:
                    if r['title'] not in seen:
                        seen.add(r['title'])
                        results.append(r)
                results = results[:max_results]
            
            if not results:
                return json.dumps({"message": "No relevant documentation found. Consider escalating to human support."})
            
            formatted = []
            for r in results:
                formatted.append({
                    "title": r['title'],
                    "content": r['content'],
                    "category": r['category']
                })
            
            return json.dumps(formatted)
            
        except Exception as e:
            logger.error(f"Error searching knowledge base: {e}")
            return json.dumps({"error": str(e)})

    async def create_ticket(self, customer_id: str, issue: str, priority: str, channel: str):
        logger.info(f"Creating ticket for customer {customer_id} with issue: {issue}")
        try:
            ticket_id = await self._execute_db_query(
                """INSERT INTO tickets (customer_id, source_channel, category, priority, status, created_at)
                   VALUES ($1, $2, $3, $4, $5, $6) RETURNING id""",
                UUID(customer_id), channel, "support", priority, "open", datetime.now(),
                fetchval=True
            )
            return json.dumps({"ticket_id": str(ticket_id)})
        except Exception as e:
            logger.error(f"Error creating ticket: {e}")
            return json.dumps({"error": str(e)})

    async def get_customer_history(self, customer_id: str):
        logger.info(f"Getting history for customer {customer_id}")
        try:
            conversations = await self._execute_db_query(
                """SELECT id, initial_channel, started_at, status FROM conversations
                   WHERE customer_id = $1 ORDER BY started_at DESC LIMIT 5""",
                UUID(customer_id)
            )
            messages = await self._execute_db_query(
                """SELECT c.id AS conversation_id, m.content, m.direction, m.role, m.created_at
                   FROM messages m JOIN conversations c ON m.conversation_id = c.id
                   WHERE c.customer_id = $1 ORDER BY m.created_at DESC LIMIT 10""",
                UUID(customer_id)
            )
            tickets = await self._execute_db_query(
                """SELECT id, source_channel, category, priority, status, created_at FROM tickets
                   WHERE customer_id = $1 ORDER BY created_at DESC LIMIT 5""",
                UUID(customer_id)
            )
            return json.dumps({
                "conversations": [dict(row) for row in conversations],
                "messages": [dict(row) for row in messages],
                "tickets": [dict(row) for row in tickets]
            }, default=str)
        except Exception as e:
            logger.error(f"Error getting customer history: {e}")
            return json.dumps({"error": str(e)})

    async def escalate_to_human(self, ticket_id: str, reason: str):
        logger.info(f"Escalating ticket {ticket_id} to human. Reason: {reason}")
        try:
            await self._execute_db_query(
                """UPDATE tickets SET status = $1, resolution_notes = COALESCE(resolution_notes, '') || $2
                   WHERE id = $3""",
                "escalated", f"\nEscalated: {reason}", UUID(ticket_id),
                execute=True
            )
            await self._execute_db_query(
                """UPDATE conversations SET status = $1, escalated_to = $2 WHERE id = (SELECT conversation_id FROM tickets WHERE id = $3)""",
                "escalated", "human", UUID(ticket_id),
                execute=True
            )
            return json.dumps({"status": "escalated", "ticket_id": str(ticket_id), "reason": reason})
        except Exception as e:
            logger.error(f"Error escalating ticket: {e}")
            return json.dumps({"error": str(e)})

    async def send_response(self, message: str, channel: str, ticket_id: str = None):
        logger.info(f"Sending response to channel {channel}: {message}")
        try:
            if ticket_id:
                conversation_id = await self._execute_db_query(
                    "SELECT conversation_id FROM tickets WHERE id = $1", UUID(ticket_id), fetchval=True
                )
                if conversation_id:
                    await self._execute_db_query(
                        "INSERT INTO messages (conversation_id, channel, direction, role, content, created_at, delivery_status) VALUES ($1, $2, $3, $4, $5, $6, $7)",
                        conversation_id, channel, "outbound", "agent", message, datetime.now(), "sent",
                        execute=True
                    )
            return json.dumps({"status": "response_sent", "channel": channel, "message": message})
        except Exception as e:
            logger.error(f"Error sending response: {e}")
            return json.dumps({"error": str(e)})

    async def run(self, message_content: str, conversation_history: list, customer_id: str, conversation_id: str, current_channel: str):
        chat_history = []
        for msg in conversation_history:
            chat_history.append({"role": msg["role"], "parts": [{"text": msg["content"]}]})

        chat_history.append({"role": "user", "parts": [{"text": message_content}]})

        escalation_keywords = ["human", "agent", "speak to someone", "transfer", "escalate", "frustrated", "unhappy"]
        needs_escalation = any(keyword in message_content.lower() for keyword in escalation_keywords)

        try:
            if needs_escalation:
                logger.info("Escalation keywords detected, attempting to escalate directly.")
                ticket_id_for_escalation = conversation_id
                tool_call = {"functionCall": {"name": "escalate_to_human", "args": {"ticket_id": str(ticket_id_for_escalation), "reason": "Customer requested human assistance or expressed high frustration."}}}
                response = self.model.generate_content(
                       contents=chat_history,
                       safety_settings={
                        "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
                        "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
                        "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
                        "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE",
                    }
                )
            else:
               response = self.model.generate_content(
                      contents=chat_history,
                      safety_settings={
                        "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
                        "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
                        "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
                        "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE",
                    }
                )

            tool_calls = []
            text_response = ""

            if response.candidates:
                for part in response.candidates[0].content.parts:
                    try:
                        if hasattr(part, 'function_call') and part.function_call:
                            tool_calls.append(part.function_call)
                        elif hasattr(part, 'text') and part.text:
                            text_response += part.text
                    except Exception as part_error:
                        logger.warning(f"Part parse error: {part_error}")
                        try:
                            text_response += str(part)
                        except:
                            pass

            if not text_response:
                try:
                    text_response = response.text
                except:
                    pass
                if not text_response:
                    try:
                        text_response = str(response.candidates[0].content.parts[0])
                    except:
                        text_response = "I understand your issue. Let me help you with that."

            if tool_calls:
                for tool_call in tool_calls:
                    tool_name = tool_call.name
                    tool_args = {k: v for k, v in tool_call.args.items()}

                    if "customer_id" in tool_args and not tool_args["customer_id"] and customer_id:
                        tool_args["customer_id"] = customer_id
                    if "channel" in tool_args and not tool_args["channel"] and current_channel:
                        tool_args["channel"] = current_channel

                    if hasattr(self, tool_name):
                        func = getattr(self, tool_name)
                        tool_result = await func(**tool_args)
                        return tool_result, tool_calls
                    else:
                        logger.warning(f"Agent tried to call unknown tool: {tool_name}")
                        return json.dumps({"error": f"Unknown tool: {tool_name}"}), []
            else:
                return json.dumps({"response": text_response}), []

        except Exception as e:
            logger.error(f"Error in agent run: {e}")
            return json.dumps({"error": str(e)}), []