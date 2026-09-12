import { ApiClient } from './client';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
export const apiClient = new ApiClient(API_URL);

export * from './client';
