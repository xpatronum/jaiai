from typing import Optional

import simplejson as json
from redis.asyncio import Redis

from jaiai.etc.pattern import singleton

JOB_TTL_SECONDS = 24 * 3600  # чтобы ключи не висели бесконечно


@singleton
class JobRegistry:

    def __init__(self, redis_url: str):
        self.r = Redis.from_url(redis_url)

    def prepare_job_for_io(self, job_id: str) -> str:
        return f"job:{job_id}"

    async def register(self, job_id: str, payload: Optional[dict] = None):
        key = self.prepare_job_for_io(job_id)
        data = {"status": "pending", "payload": payload or {}}
        # HSET + EXPIRE атомарно через pipeline/transaction
        async with self.r.pipeline(transaction=True) as p:
            p.hset(
                key,
                mapping={"status": "pending", "payload": json.dumps(data["payload"])},
            )
            p.expire(key, JOB_TTL_SECONDS)
            await p.execute()

    async def mark_done(self, job_id: str, result: Optional[dict] = None):
        key = self.prepare_job_for_io(job_id)
        mapping = {"status": "done"}
        if result:
            mapping["payload"] = json.dumps(result)
        async with self.r.pipeline(transaction=True) as p:
            p.hset(key, mapping=mapping)
            p.expire(key, JOB_TTL_SECONDS)
            await p.execute()

    async def is_done(self, job_id: str) -> bool:
        key = self.prepare_job_for_io(job_id)
        status = await self.r.hget(key, "status")  # type: ignore
        return status is not None and status.decode() == "done"

    async def get(self, job_id: str) -> Optional[dict]:
        key = self.prepare_job_for_io(job_id)
        data = await self.r.hgetall(key)
        if not data:
            return None
        payload = data.get(b"payload")
        return json.loads(payload.decode()) if payload else {}
