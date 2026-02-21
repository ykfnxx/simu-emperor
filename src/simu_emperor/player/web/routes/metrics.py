"""Prometheus 指标端点。"""
from fastapi import APIRouter
from fastapi.responses import Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
async def prometheus_metrics():
    """Prometheus 格式指标端点。

    此端点供 Prometheus 或 Grafana 抓取指标数据。
    """
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
