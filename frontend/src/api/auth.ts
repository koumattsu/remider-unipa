import apiClient from './client';
import { User } from '../types';

export const authApi = {
  getCurrentUser: async (): Promise<User> => {
    const response = await apiClient.get('/api/v1/auth/me');
    return response.data;
  },
};

