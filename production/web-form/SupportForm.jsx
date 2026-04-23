
import React, { useState } from 'react';
import axios from 'axios';

const categories = ['general', 'technical', 'billing', 'bug_report', 'feedback'];
const priorities = ['low', 'medium', 'high', 'urgent'];

const SupportForm = () => {
    const [formData, setFormData] = useState({
        name: '',
        email: '',
        subject: '',
        category: categories[0],
        priority: priorities[0],
        message: '',
    });
    const [errors, setErrors] = useState({});
    const [loading, setLoading] = useState(false);
    const [submissionSuccess, setSubmissionSuccess] = useState(false);
    const [ticketId, setTicketId] = useState(null);
    const [submissionMessage, setSubmissionMessage] = useState('');
    const [charCount, setCharCount] = useState(0);

    const validateForm = () => {
        const newErrors = {};
        if (formData.name.length < 2) {
            newErrors.name = 'Name must be at least 2 characters';
        }
        if (!/^[\w-.]+@([\w-]+\.)+[\w-]{2,4}$/.test(formData.email)) {
            newErrors.email = 'Invalid email address';
        }
        if (formData.subject.length < 5) {
            newErrors.subject = 'Subject must be at least 5 characters';
        }
        if (formData.message.length < 10) {
            newErrors.message = 'Message must be at least 10 characters';
        }
        setErrors(newErrors);
        return Object.keys(newErrors).length === 0;
    };

    const handleChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => ({
            ...prev,
            [name]: value
        }));
        if (name === 'message') {
            setCharCount(value.length);
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!validateForm()) {
            return;
        }

        setLoading(true);
        setErrors({});
        try {
            const response = await axios.post('/api/support/submit', formData);
            setTicketId(response.data.ticket_id);
            setSubmissionMessage(response.data.message);
            setSubmissionSuccess(true);
        } catch (error) {
            console.error('Submission error:', error);
            setErrors({ general: error.response?.data?.detail || 'An unexpected error occurred.' });
        } finally {
            setLoading(false);
        }
    };

    const handleResetForm = () => {
        setFormData({
            name: '',
            email: '',
            subject: '',
            category: categories[0],
            priority: priorities[0],
            message: '',
        });
        setErrors({});
        setLoading(false);
        setSubmissionSuccess(false);
        setTicketId(null);
        setSubmissionMessage('');
        setCharCount(0);
    };

    if (submissionSuccess) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-gray-100 p-4">
                <div className="bg-white p-8 rounded-lg shadow-md w-full max-w-md text-center">
                    <h2 className="text-2xl font-bold mb-4 text-green-600">Submission Successful!</h2>
                    <p className="text-gray-700 mb-2">{submissionMessage}</p>
                    <p className="text-gray-700 mb-4">Your Ticket ID is: <span className="font-semibold">{ticketId}</span></p>
                    <button
                        onClick={handleResetForm}
                        className="w-full bg-blue-500 text-white p-3 rounded-md hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-50"
                    >
                        Submit Another Request
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen flex items-center justify-center bg-gray-100 p-4">
            <div className="bg-white p-8 rounded-lg shadow-md w-full max-w-md">
                <h2 className="text-2xl font-bold mb-6 text-gray-800 text-center">Customer Support Request</h2>

                <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                        <label htmlFor="name" className="block text-sm font-medium text-gray-700">Name</label>
                        <input
                            type="text"
                            id="name"
                            name="name"
                            value={formData.name}
                            onChange={handleChange}
                            className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                        />
                        {errors.name && <p className="text-red-500 text-xs mt-1">{errors.name}</p>}
                    </div>

                    <div>
                        <label htmlFor="email" className="block text-sm font-medium text-gray-700">Email</label>
                        <input
                            type="email"
                            id="email"
                            name="email"
                            value={formData.email}
                            onChange={handleChange}
                            className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                        />
                        {errors.email && <p className="text-red-500 text-xs mt-1">{errors.email}</p>}
                    </div>

                    <div>
                        <label htmlFor="subject" className="block text-sm font-medium text-gray-700">Subject</label>
                        <input
                            type="text"
                            id="subject"
                            name="subject"
                            value={formData.subject}
                            onChange={handleChange}
                            className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                        />
                        {errors.subject && <p className="text-red-500 text-xs mt-1">{errors.subject}</p>}
                    </div>

                    <div>
                        <label htmlFor="category" className="block text-sm font-medium text-gray-700">Category</label>
                        <select
                            id="category"
                            name="category"
                            value={formData.category}
                            onChange={handleChange}
                            className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                        >
                            {categories.map(cat => (
                                <option key={cat} value={cat}>{cat.replace('_', ' ').toUpperCase()}</option>
                            ))}
                        </select>
                    </div>

                    <div>
                        <label htmlFor="priority" className="block text-sm font-medium text-gray-700">Priority</label>
                        <select
                            id="priority"
                            name="priority"
                            value={formData.priority}
                            onChange={handleChange}
                            className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                        >
                            {priorities.map(prio => (
                                <option key={prio} value={prio}>{prio.toUpperCase()}</option>
                            ))}
                        </select>
                    </div>

                    <div>
                        <label htmlFor="message" className="block text-sm font-medium text-gray-700">Message</label>
                        <textarea
                            id="message"
                            name="message"
                            rows="5"
                            value={formData.message}
                            onChange={handleChange}
                            className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                        ></textarea>
                        <p className="text-right text-xs text-gray-500">{charCount}/500</p>
                        {errors.message && <p className="text-red-500 text-xs mt-1">{errors.message}</p>}
                    </div>

                    {errors.general && <p className="text-red-500 text-sm mb-4">{errors.general}</p>}

                    <button
                        type="submit"
                        disabled={loading}
                        className="w-full bg-indigo-600 text-white p-3 rounded-md hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-opacity-50 disabled:opacity-50"
                    >
                        {loading ? 'Submitting...' : 'Submit Request'}
                    </button>
                </form>
            </div>
        </div>
    );
};

export default SupportForm;
