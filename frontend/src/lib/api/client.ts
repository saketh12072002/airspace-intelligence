import { HealthResponse, AircraftList } from '@/types';

export class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl.endsWith('/') ? baseUrl.slice(0, -1) : baseUrl;
  }

  async healthCheck(): Promise<HealthResponse> {
    try {
      const response = await fetch(`${this.baseUrl}/health`);
      if (!response.ok) {
        throw new Error(`Health check failed with status: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error('API health check error:', error);
      throw error;
    }
  }

  async getAircraft(): Promise<AircraftList> {
    try {
      // TODO: Implement actual endpoint call, for now return placeholder
      return { count: 0, aircraft: [] };
    } catch (error) {
      console.error('Failed to get aircraft:', error);
      return { count: 0, aircraft: [] };
    }
  }
}
