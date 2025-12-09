// frontend/src/api/auth.ts

import apiClient from './client';
// import { User } from '../types';

export const authApi = {
  // 型指定を外す（あとでUser型をちゃんと定義したくなったら戻せばOK）
  // getCurrentUser: async (): Promise<User> => {
  getCurrentUser: async () => {
    const response = await apiClient.get('/api/v1/auth/me');
    return response.data;
  },
};