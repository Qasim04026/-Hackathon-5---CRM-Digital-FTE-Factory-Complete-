
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(50) UNIQUE,
    name VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_customers_email ON customers (email);
CREATE INDEX idx_customers_phone ON customers (phone);

CREATE TABLE customer_identifiers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    identifier_type VARCHAR(50) NOT NULL, -- e.g., "email", "phone", "external_id"
    identifier_value VARCHAR(255) NOT NULL,
    verified BOOLEAN DEFAULT FALSE,
    UNIQUE (identifier_type, identifier_value)
);

CREATE INDEX idx_customer_identifiers_customer_id ON customer_identifiers (customer_id);
CREATE INDEX idx_customer_identifiers_type_value ON customer_identifiers (identifier_type, identifier_value);

CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    initial_channel VARCHAR(50) NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(50) DEFAULT 'open', -- e.g., "open", "closed", "escalated"
    sentiment_score DECIMAL(3, 2), -- e.g., -1.00 to 1.00
    escalated_to VARCHAR(255), -- e.g., "human_agent_id", "department_name"
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_conversations_customer_id ON conversations (customer_id);
CREATE INDEX idx_conversations_status ON conversations (status);
CREATE INDEX idx_conversations_started_at ON conversations (started_at);

CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    channel VARCHAR(50) NOT NULL,
    direction VARCHAR(10) NOT NULL, -- "inbound" or "outbound"
    role VARCHAR(50) NOT NULL, -- "user", "agent", "system"
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    tokens_used INTEGER,
    latency_ms INTEGER,
    tool_calls JSONB,
    channel_message_id VARCHAR(255), -- ID from the specific channel (e.g., Gmail message ID, Twilio SID)
    delivery_status VARCHAR(50) -- e.g., "sent", "delivered", "read", "failed"
);

CREATE INDEX idx_messages_conversation_id ON messages (conversation_id);
CREATE INDEX idx_messages_created_at ON messages (created_at);

CREATE TABLE tickets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    source_channel VARCHAR(50) NOT NULL,
    category VARCHAR(100),
    priority VARCHAR(50) DEFAULT 'medium', -- e.g., "low", "medium", "high", "urgent"
    status VARCHAR(50) DEFAULT 'open', -- e.g., "open", "pending", "resolved", "closed"
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolution_notes TEXT
);

CREATE INDEX idx_tickets_customer_id ON tickets (customer_id);
CREATE INDEX idx_tickets_conversation_id ON tickets (conversation_id);
CREATE INDEX idx_tickets_status ON tickets (status);
CREATE INDEX idx_tickets_priority ON tickets (priority);

CREATE TABLE knowledge_base (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    category VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_knowledge_base_title ON knowledge_base (title);
CREATE INDEX idx_knowledge_base_category ON knowledge_base (category);
CREATE TEXT SEARCH DICTIONARY english_stem_dict (
    TEMPLATE = snowball, LANGUAGE = english
);
CREATE TEXT SEARCH CONFIGURATION english_stem (COPY = english);
ALTER TEXT SEARCH CONFIGURATION english_stem
    ALTER MAPPING FOR asciiword, hword, hword_asciipart, hword_numpart, numhword, word
    WITH english_stem_dict;

ALTER TABLE knowledge_base ADD COLUMN tsv_content TSVECTOR;

UPDATE knowledge_base SET tsv_content = to_tsvector('english_stem', content);

CREATE FUNCTION update_knowledge_base_tsv() RETURNS TRIGGER AS $$
BEGIN
    NEW.tsv_content = to_tsvector('english_stem', NEW.content);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_knowledge_base_tsv_trigger
BEFORE INSERT OR UPDATE OF content ON knowledge_base
FOR EACH ROW EXECUTE FUNCTION update_knowledge_base_tsv();

CREATE INDEX idx_knowledge_base_tsv_content ON knowledge_base USING GIN (tsv_content);

CREATE TABLE channel_configs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    channel VARCHAR(50) UNIQUE NOT NULL, -- e.g., "email", "whatsapp", "webform"
    enabled BOOLEAN DEFAULT TRUE,
    config JSONB DEFAULT '{}', -- channel-specific settings
    response_template TEXT,
    max_response_length INTEGER
);

CREATE UNIQUE INDEX idx_channel_configs_channel ON channel_configs (channel);

CREATE TABLE agent_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    metric_name VARCHAR(100) NOT NULL,
    metric_value DECIMAL(10, 2) NOT NULL,
    channel VARCHAR(50),
    dimensions JSONB DEFAULT '{}', -- additional dimensions like "tool_used", "escalation_type"
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_agent_metrics_name_channel ON agent_metrics (metric_name, channel);
CREATE INDEX idx_agent_metrics_recorded_at ON agent_metrics (recorded_at);
