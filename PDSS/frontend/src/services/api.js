import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000',
  timeout: 30000
});

export const apiClient = {
  getVendors: async () => (await api.get('/vendors')).data,
  getDashboardSummary: async () => (await api.get('/dashboard-summary')).data,
  getForecast: async (vendorId) => (await api.get(`/forecast/${vendorId}`)).data,
  getRecommendation: async () => (await api.get('/recommend-best-vendor')).data,
  predictDelay: async (payload) => (await api.post('/predict-delay', payload)).data,
  predictRisk: async (payload) => (await api.post('/predict-risk', payload)).data
};

export default api;
