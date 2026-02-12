// frontend/src/api/tasks.ts

import apiClient from './client';
import { Task, TaskCreate, TaskUpdate } from '../types';

export const tasksApi = {
  getAll: async (params?: {
    start_date?: string;
    end_date?: string;
    is_done?: boolean;
  }): Promise<Task[]> => {
    const response = await apiClient.get('/tasks', { params });
    return response.data;
  },

  create: async (task: TaskCreate): Promise<Task> => {
    const response = await apiClient.post('/tasks/', task);
    return response.data;
  },

  update: async (taskId: number, task: TaskUpdate): Promise<Task> => {
    const response = await apiClient.patch(`/tasks/${taskId}`, task);
    return response.data;
  },

  delete: async (taskId: number): Promise<void> => {
    await apiClient.delete(`/tasks/${taskId}`);
  },
};