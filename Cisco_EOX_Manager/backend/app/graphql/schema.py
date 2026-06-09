from __future__ import annotations

from typing import Optional

import strawberry
from strawberry.scalars import JSON

from app.db.models import PidCatalog, ProductEox
from app.db.session import make_session
from app.services.eox_orchestrator import catalog_to_out, product_to_out
from app.services.normalization import normalize_pid


@strawberry.type
class EoxProductType:
    pid: str
    normalized_pid: str
    technology: Optional[str]
    status: str
    source: str
    end_of_sale_date: Optional[str]
    last_date_of_support: Optional[str]
    end_of_sw_maintenance: Optional[str]
    end_of_security_support: Optional[str]
    end_of_routine_failure_analysis: Optional[str]
    eox_announcement_url: Optional[str]
    product_bulletin_url: Optional[str]
    lookup_count: int
    payload: JSON


@strawberry.type
class PidCatalogType:
    pid: str
    normalized_pid: str
    technology: Optional[str]
    category_name: Optional[str]
    product_name: Optional[str]
    product_url: Optional[str]
    is_eox: bool
    source: str
    payload: JSON


def _to_product_graph(product: ProductEox) -> EoxProductType:
    output = product_to_out(product)
    return EoxProductType(
        pid=output.pid,
        normalized_pid=output.normalized_pid,
        technology=output.technology,
        status=output.status,
        source=output.source,
        end_of_sale_date=output.end_of_sale_date,
        last_date_of_support=output.last_date_of_support,
        end_of_sw_maintenance=output.end_of_sw_maintenance,
        end_of_security_support=output.end_of_security_support,
        end_of_routine_failure_analysis=output.end_of_routine_failure_analysis,
        eox_announcement_url=output.eox_announcement_url,
        product_bulletin_url=output.product_bulletin_url,
        lookup_count=output.lookup_count,
        payload=output.payload,
    )


def _to_catalog_graph(entry: PidCatalog) -> PidCatalogType:
    output = catalog_to_out(entry)
    return PidCatalogType(
        pid=output.pid,
        normalized_pid=output.normalized_pid,
        technology=output.technology,
        category_name=output.category_name,
        product_name=output.product_name,
        product_url=output.product_url,
        is_eox=output.is_eox,
        source=output.source,
        payload=output.payload,
    )


@strawberry.type
class Query:
    @strawberry.field
    def product(self, pid: str) -> Optional[EoxProductType]:
        with make_session() as db:
            product = db.query(ProductEox).filter(ProductEox.normalized_pid == normalize_pid(pid)).one_or_none()
            return _to_product_graph(product) if product else None

    @strawberry.field
    def products(self, search: Optional[str] = None, limit: int = 25, offset: int = 0) -> list[EoxProductType]:
        with make_session() as db:
            query = db.query(ProductEox)
            if search:
                like = f"%{search.strip()}%"
                query = query.filter(
                    (ProductEox.pid.ilike(like))
                    | (ProductEox.normalized_pid.ilike(like))
                    | (ProductEox.technology.ilike(like))
                )
            items = query.order_by(ProductEox.updated_at.desc()).offset(offset).limit(min(limit, 100)).all()
            return [_to_product_graph(item) for item in items]

    @strawberry.field
    def pid_catalog(self, search: Optional[str] = None, limit: int = 25, offset: int = 0) -> list[PidCatalogType]:
        with make_session() as db:
            query = db.query(PidCatalog)
            if search:
                like = f"%{search.strip()}%"
                query = query.filter(
                    (PidCatalog.pid.ilike(like))
                    | (PidCatalog.normalized_pid.ilike(like))
                    | (PidCatalog.technology.ilike(like))
                    | (PidCatalog.category_name.ilike(like))
                    | (PidCatalog.product_name.ilike(like))
                )
            items = query.order_by(PidCatalog.updated_at.desc()).offset(offset).limit(min(limit, 100)).all()
            return [_to_catalog_graph(item) for item in items]


schema = strawberry.Schema(query=Query)
