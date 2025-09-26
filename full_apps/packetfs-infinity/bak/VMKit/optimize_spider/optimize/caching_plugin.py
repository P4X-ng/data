import redis
import psycopg2
from fastapi import Request, Response

class CachingPlugin:
    def __init__(self, redis_url, postgres_conn_str):
        self.redis = redis.Redis.from_url(redis_url)
        self.postgres = psycopg2.connect(postgres_conn_str)
        self.postgres_cursor = self.postgres.cursor()
        print(f"Initializing {self.__name__}")

    def cache_request(self, key, value):
        # Cache response in Redis
        self.redis.set(key, value)

    def get_cache(self, key):
        # Get cached response
        return self.redis.get(key)

    def log_request(self, method, url, status_code):
        # Log request details in PostgreSQL
        query = """INSERT INTO request_logs (method, url, status_code)
                   VALUES (%s, %s, %s)"""
        self.postgres_cursor.execute(query, (method, url, status_code))
        self.postgres.commit()

    async def handle_request(self, request: Request, response: Response):
        key = request.url.path

        cached_response = self.get_cache(key)
        if cached_response:
            return Response(content=cached_response, media_type='application/json')

        # Log request
        self.log_request(request.method, str(request.url), response.status_code)

        # Cache the response
        self.cache_request(key, response.body)
        return response
