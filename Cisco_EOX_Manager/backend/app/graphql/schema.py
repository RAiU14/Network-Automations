from __future__ import annotations

from typing import Optional

import strawberry
from sqlalchemy import or_
from strawberry.scalars import JSON

from app.db.models import (
    AutoPopCheckpoint,
    AutoPopJob,
    ExportJob,
    EoxAffectedProduct,
    EoxAnnouncement,
    EoxAnnouncementTable,
    PidCatalog,
    ProductEox,
    SeedRun,
    SystemEvent,
)
from app.db.session import make_session
from app.services.eox_orchestrator import catalog_to_out, product_to_out
from app.services.normalization import normalize_pid


def _dt(value: object) -> Optional[str]:
    return value.isoformat() if hasattr(value, "isoformat") else None


def _bounded_limit(value: int, maximum: int = 500) -> int:
    return max(1, min(int(value or 25), maximum))


@strawberry.type
class EoxProductType:
    pid: str
    normalized_pid: str
    technology: Optional[str]
    product_name: Optional[str]
    series: Optional[str]
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
    last_lookup_at: Optional[str]
    last_scraped_at: Optional[str]
    updated_at: Optional[str]
    payload: JSON
    raw_response: JSON


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
    updated_at: Optional[str]
    payload: JSON


@strawberry.type
class EoxAnnouncementType:
    id: int
    announcement_url: str
    announcement_name: Optional[str]
    title: Optional[str]
    product_bulletin_url: Optional[str]
    technology: Optional[str]
    series: Optional[str]
    series_url: Optional[str]
    source: str
    content_hash: Optional[str]
    first_seen_at: Optional[str]
    last_seen_at: Optional[str]
    updated_at: Optional[str]
    payload: JSON
    raw_response: JSON


@strawberry.type
class EoxAnnouncementTableType:
    id: int
    announcement_id: int
    table_index: int
    heading: Optional[str]
    caption: Optional[str]
    content_hash: Optional[str]
    headers: JSON
    rows: JSON
    raw_table: JSON
    updated_at: Optional[str]


@strawberry.type
class EoxAffectedProductType:
    id: int
    announcement_id: int
    product_id: Optional[int]
    pid: str
    normalized_pid: str
    technology: Optional[str]
    product_description: Optional[str]
    source: str
    table_index: int
    row_index: int
    row_hash: str
    updated_at: Optional[str]
    payload: JSON
    raw_response: JSON


@strawberry.type
class AutoPopCheckpointType:
    id: int
    scope: str
    scope_key: str
    status: str
    last_started_at: Optional[str]
    last_completed_at: Optional[str]
    last_success_at: Optional[str]
    next_allowed_at: Optional[str]
    run_count: int
    skip_count: int
    catalog_records: int
    eox_records: int
    announcements_seen: int
    last_error: Optional[str]
    stats: JSON
    updated_at: Optional[str]


@strawberry.type
class SeedRunType:
    id: int
    source: Optional[str]
    source_path: Optional[str]
    mode: str
    status: str
    started_at: Optional[str]
    finished_at: Optional[str]
    stats: JSON


@strawberry.type
class SystemEventType:
    id: int
    level: str
    event_type: str
    source: Optional[str]
    message: str
    payload: JSON
    created_at: Optional[str]

@strawberry.type
class AutoPopJobType:
    id: int
    status: str
    requested_by: Optional[str]
    parameters: JSON
    command: JSON
    log_file: Optional[str]
    process_id: Optional[int]
    return_code: Optional[int]
    stats: JSON
    last_error: Optional[str]
    started_at: Optional[str]
    finished_at: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]


@strawberry.type
class ExportJobType:
    id: int
    dataset: str
    format: str
    status: str
    row_count: int
    requested_by: Optional[str]
    parameters: JSON
    file_name: Optional[str]
    last_error: Optional[str]
    created_at: Optional[str]



@strawberry.type
class DatabaseOverviewType:
    total_products: int
    total_catalog_entries: int
    total_announcements: int
    total_announcement_tables: int
    total_affected_products: int
    total_seed_runs: int
    total_checkpoints: int
    total_system_events: int
    total_autopop_jobs: int
    total_export_jobs: int


@strawberry.type
class ProductEvidenceType:
    product: Optional[EoxProductType]
    affected_products: list[EoxAffectedProductType]
    announcements: list[EoxAnnouncementType]
    tables: list[EoxAnnouncementTableType]


def _to_product_graph(product: ProductEox) -> EoxProductType:
    output = product_to_out(product)
    return EoxProductType(
        pid=output.pid,
        normalized_pid=output.normalized_pid,
        technology=output.technology,
        product_name=output.product_name,
        series=output.series,
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
        last_lookup_at=_dt(output.last_lookup_at),
        last_scraped_at=_dt(output.last_scraped_at),
        updated_at=_dt(output.updated_at),
        payload=output.payload,
        raw_response=product.raw_response or {},
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
        updated_at=_dt(output.updated_at),
        payload=output.payload,
    )


def _to_announcement_graph(item: EoxAnnouncement) -> EoxAnnouncementType:
    return EoxAnnouncementType(
        id=item.id,
        announcement_url=item.announcement_url,
        announcement_name=item.announcement_name,
        title=item.title,
        product_bulletin_url=item.product_bulletin_url,
        technology=item.technology,
        series=item.series,
        series_url=item.series_url,
        source=item.source,
        content_hash=item.content_hash,
        first_seen_at=_dt(item.first_seen_at),
        last_seen_at=_dt(item.last_seen_at),
        updated_at=_dt(item.updated_at),
        payload=item.payload or {},
        raw_response=item.raw_response or {},
    )


def _to_table_graph(item: EoxAnnouncementTable) -> EoxAnnouncementTableType:
    return EoxAnnouncementTableType(
        id=item.id,
        announcement_id=item.announcement_id,
        table_index=item.table_index,
        heading=item.heading,
        caption=item.caption,
        content_hash=item.content_hash,
        headers=item.headers or [],
        rows=item.rows or [],
        raw_table=item.raw_table or {},
        updated_at=_dt(item.updated_at),
    )


def _to_affected_graph(item: EoxAffectedProduct) -> EoxAffectedProductType:
    return EoxAffectedProductType(
        id=item.id,
        announcement_id=item.announcement_id,
        product_id=item.product_id,
        pid=item.pid,
        normalized_pid=item.normalized_pid,
        technology=item.technology,
        product_description=item.product_description,
        source=item.source,
        table_index=item.table_index,
        row_index=item.row_index,
        row_hash=item.row_hash,
        updated_at=_dt(item.updated_at),
        payload=item.payload or {},
        raw_response=item.raw_response or {},
    )


def _to_checkpoint_graph(item: AutoPopCheckpoint) -> AutoPopCheckpointType:
    return AutoPopCheckpointType(
        id=item.id,
        scope=item.scope,
        scope_key=item.scope_key,
        status=item.status,
        last_started_at=_dt(item.last_started_at),
        last_completed_at=_dt(item.last_completed_at),
        last_success_at=_dt(item.last_success_at),
        next_allowed_at=_dt(item.next_allowed_at),
        run_count=item.run_count or 0,
        skip_count=item.skip_count or 0,
        catalog_records=item.catalog_records or 0,
        eox_records=item.eox_records or 0,
        announcements_seen=item.announcements_seen or 0,
        last_error=item.last_error,
        stats=item.stats or {},
        updated_at=_dt(item.updated_at),
    )


def _to_seed_run_graph(item: SeedRun) -> SeedRunType:
    return SeedRunType(
        id=item.id,
        source=item.source,
        source_path=item.source_path,
        mode=item.mode,
        status=item.status,
        started_at=_dt(item.started_at),
        finished_at=_dt(item.finished_at),
        stats=item.stats or {},
    )


def _to_system_event_graph(item: SystemEvent) -> SystemEventType:
    return SystemEventType(
        id=item.id,
        level=item.level,
        event_type=item.event_type,
        source=item.source,
        message=item.message,
        payload=item.payload or {},
        created_at=_dt(item.created_at),
    )


def _to_autopop_job_graph(item: AutoPopJob) -> AutoPopJobType:
    return AutoPopJobType(
        id=item.id,
        status=item.status,
        requested_by=item.requested_by,
        parameters=item.parameters or {},
        command=item.command or [],
        log_file=item.log_file,
        process_id=item.process_id,
        return_code=item.return_code,
        stats=item.stats or {},
        last_error=item.last_error,
        started_at=_dt(item.started_at),
        finished_at=_dt(item.finished_at),
        created_at=_dt(item.created_at),
        updated_at=_dt(item.updated_at),
    )


def _to_export_job_graph(item: ExportJob) -> ExportJobType:
    return ExportJobType(
        id=item.id,
        dataset=item.dataset,
        format=item.format,
        status=item.status,
        row_count=item.row_count or 0,
        requested_by=item.requested_by,
        parameters=item.parameters or {},
        file_name=item.file_name,
        last_error=item.last_error,
        created_at=_dt(item.created_at),
    )


@strawberry.type
class Query:
    @strawberry.field
    def database_overview(self) -> DatabaseOverviewType:
        with make_session() as db:
            return DatabaseOverviewType(
                total_products=db.query(ProductEox).count(),
                total_catalog_entries=db.query(PidCatalog).count(),
                total_announcements=db.query(EoxAnnouncement).count(),
                total_announcement_tables=db.query(EoxAnnouncementTable).count(),
                total_affected_products=db.query(EoxAffectedProduct).count(),
                total_seed_runs=db.query(SeedRun).count(),
                total_checkpoints=db.query(AutoPopCheckpoint).count(),
                total_system_events=db.query(SystemEvent).count(),
                total_autopop_jobs=db.query(AutoPopJob).count(),
                total_export_jobs=db.query(ExportJob).count(),
            )

    @strawberry.field
    def product(self, pid: str) -> Optional[EoxProductType]:
        with make_session() as db:
            product = db.query(ProductEox).filter(ProductEox.normalized_pid == normalize_pid(pid)).one_or_none()
            return _to_product_graph(product) if product else None

    @strawberry.field
    def product_json(self, pid: str) -> Optional[JSON]:
        with make_session() as db:
            product = db.query(ProductEox).filter(ProductEox.normalized_pid == normalize_pid(pid)).one_or_none()
            if not product:
                return None
            affected = db.query(EoxAffectedProduct).filter(EoxAffectedProduct.product_id == product.id).all()
            return {
                "product": product.payload or {},
                "raw_response": product.raw_response or {},
                "affected_products": [item.payload or {} for item in affected],
            }

    @strawberry.field
    def product_evidence(self, pid: str) -> ProductEvidenceType:
        with make_session() as db:
            normalized = normalize_pid(pid)
            product = db.query(ProductEox).filter(ProductEox.normalized_pid == normalized).one_or_none()
            affected = (
                db.query(EoxAffectedProduct)
                .filter(EoxAffectedProduct.normalized_pid == normalized)
                .order_by(EoxAffectedProduct.updated_at.desc())
                .limit(200)
                .all()
            )
            if product and product.id:
                seen_ids = {item.id for item in affected}
                extra = (
                    db.query(EoxAffectedProduct)
                    .filter(EoxAffectedProduct.product_id == product.id)
                    .order_by(EoxAffectedProduct.updated_at.desc())
                    .limit(200)
                    .all()
                )
                affected.extend(item for item in extra if item.id not in seen_ids)
            announcement_ids = sorted({item.announcement_id for item in affected if item.announcement_id})
            if not announcement_ids and product and product.eox_announcement_url:
                announcement = db.query(EoxAnnouncement).filter(EoxAnnouncement.announcement_url == product.eox_announcement_url).one_or_none()
                if announcement:
                    announcement_ids = [announcement.id]
            announcements = db.query(EoxAnnouncement).filter(EoxAnnouncement.id.in_(announcement_ids)).all() if announcement_ids else []
            tables = (
                db.query(EoxAnnouncementTable)
                .filter(EoxAnnouncementTable.announcement_id.in_(announcement_ids))
                .order_by(EoxAnnouncementTable.announcement_id.asc(), EoxAnnouncementTable.table_index.asc())
                .all()
                if announcement_ids
                else []
            )
            return ProductEvidenceType(
                product=_to_product_graph(product) if product else None,
                affected_products=[_to_affected_graph(item) for item in affected],
                announcements=[_to_announcement_graph(item) for item in announcements],
                tables=[_to_table_graph(item) for item in tables],
            )

    @strawberry.field
    def products(self, search: Optional[str] = None, limit: int = 25, offset: int = 0) -> list[EoxProductType]:
        with make_session() as db:
            query = db.query(ProductEox)
            if search:
                like = f"%{search.strip()}%"
                query = query.filter(or_(ProductEox.pid.ilike(like), ProductEox.normalized_pid.ilike(like), ProductEox.technology.ilike(like), ProductEox.status.ilike(like)))
            items = query.order_by(ProductEox.updated_at.desc()).offset(offset).limit(_bounded_limit(limit)).all()
            return [_to_product_graph(item) for item in items]

    @strawberry.field
    def pid_catalog(self, search: Optional[str] = None, limit: int = 25, offset: int = 0) -> list[PidCatalogType]:
        with make_session() as db:
            query = db.query(PidCatalog)
            if search:
                like = f"%{search.strip()}%"
                query = query.filter(or_(PidCatalog.pid.ilike(like), PidCatalog.normalized_pid.ilike(like), PidCatalog.technology.ilike(like), PidCatalog.category_name.ilike(like), PidCatalog.product_name.ilike(like)))
            items = query.order_by(PidCatalog.updated_at.desc()).offset(offset).limit(_bounded_limit(limit)).all()
            return [_to_catalog_graph(item) for item in items]

    @strawberry.field
    def announcement(self, id: Optional[int] = None, announcement_url: Optional[str] = None) -> Optional[EoxAnnouncementType]:
        with make_session() as db:
            query = db.query(EoxAnnouncement)
            if id is not None:
                item = query.filter(EoxAnnouncement.id == id).one_or_none()
            elif announcement_url:
                item = query.filter(EoxAnnouncement.announcement_url == announcement_url).one_or_none()
            else:
                item = None
            return _to_announcement_graph(item) if item else None

    @strawberry.field
    def announcements(self, search: Optional[str] = None, limit: int = 25, offset: int = 0) -> list[EoxAnnouncementType]:
        with make_session() as db:
            query = db.query(EoxAnnouncement)
            if search:
                like = f"%{search.strip()}%"
                query = query.filter(or_(EoxAnnouncement.announcement_name.ilike(like), EoxAnnouncement.title.ilike(like), EoxAnnouncement.technology.ilike(like), EoxAnnouncement.series.ilike(like), EoxAnnouncement.announcement_url.ilike(like)))
            items = query.order_by(EoxAnnouncement.updated_at.desc()).offset(offset).limit(_bounded_limit(limit)).all()
            return [_to_announcement_graph(item) for item in items]

    @strawberry.field
    def announcement_tables(self, announcement_id: Optional[int] = None, announcement_url: Optional[str] = None, limit: int = 100, offset: int = 0) -> list[EoxAnnouncementTableType]:
        with make_session() as db:
            query = db.query(EoxAnnouncementTable)
            if announcement_id is not None:
                query = query.filter(EoxAnnouncementTable.announcement_id == announcement_id)
            elif announcement_url:
                announcement = db.query(EoxAnnouncement).filter(EoxAnnouncement.announcement_url == announcement_url).one_or_none()
                if not announcement:
                    return []
                query = query.filter(EoxAnnouncementTable.announcement_id == announcement.id)
            items = query.order_by(EoxAnnouncementTable.announcement_id.desc(), EoxAnnouncementTable.table_index.asc()).offset(offset).limit(_bounded_limit(limit)).all()
            return [_to_table_graph(item) for item in items]

    @strawberry.field
    def affected_products(self, pid: Optional[str] = None, announcement_url: Optional[str] = None, search: Optional[str] = None, limit: int = 50, offset: int = 0) -> list[EoxAffectedProductType]:
        with make_session() as db:
            query = db.query(EoxAffectedProduct)
            if pid:
                query = query.filter(EoxAffectedProduct.normalized_pid == normalize_pid(pid))
            if announcement_url:
                announcement = db.query(EoxAnnouncement).filter(EoxAnnouncement.announcement_url == announcement_url).one_or_none()
                if not announcement:
                    return []
                query = query.filter(EoxAffectedProduct.announcement_id == announcement.id)
            if search:
                like = f"%{search.strip()}%"
                query = query.filter(or_(EoxAffectedProduct.pid.ilike(like), EoxAffectedProduct.normalized_pid.ilike(like), EoxAffectedProduct.technology.ilike(like), EoxAffectedProduct.product_description.ilike(like)))
            items = query.order_by(EoxAffectedProduct.updated_at.desc()).offset(offset).limit(_bounded_limit(limit)).all()
            return [_to_affected_graph(item) for item in items]

    @strawberry.field
    def auto_pop_checkpoints(self, scope: Optional[str] = None, limit: int = 100, offset: int = 0) -> list[AutoPopCheckpointType]:
        with make_session() as db:
            query = db.query(AutoPopCheckpoint)
            if scope:
                query = query.filter(AutoPopCheckpoint.scope == scope)
            items = query.order_by(AutoPopCheckpoint.updated_at.desc()).offset(offset).limit(_bounded_limit(limit)).all()
            return [_to_checkpoint_graph(item) for item in items]

    @strawberry.field
    def seed_runs(self, status: Optional[str] = None, limit: int = 50, offset: int = 0) -> list[SeedRunType]:
        with make_session() as db:
            query = db.query(SeedRun)
            if status:
                query = query.filter(SeedRun.status == status)
            items = query.order_by(SeedRun.started_at.desc()).offset(offset).limit(_bounded_limit(limit)).all()
            return [_to_seed_run_graph(item) for item in items]

    @strawberry.field
    def system_events(self, level: Optional[str] = None, event_type: Optional[str] = None, limit: int = 100, offset: int = 0) -> list[SystemEventType]:
        with make_session() as db:
            query = db.query(SystemEvent)
            if level:
                query = query.filter(SystemEvent.level == level.lower())
            if event_type:
                query = query.filter(SystemEvent.event_type == event_type)
            items = query.order_by(SystemEvent.created_at.desc()).offset(offset).limit(_bounded_limit(limit)).all()
            return [_to_system_event_graph(item) for item in items]

    @strawberry.field
    def auto_pop_jobs(self, status: Optional[str] = None, limit: int = 50, offset: int = 0) -> list[AutoPopJobType]:
        with make_session() as db:
            query = db.query(AutoPopJob)
            if status:
                query = query.filter(AutoPopJob.status == status)
            items = query.order_by(AutoPopJob.created_at.desc()).offset(offset).limit(_bounded_limit(limit)).all()
            return [_to_autopop_job_graph(item) for item in items]

    @strawberry.field
    def export_jobs(self, dataset: Optional[str] = None, limit: int = 50, offset: int = 0) -> list[ExportJobType]:
        with make_session() as db:
            query = db.query(ExportJob)
            if dataset:
                query = query.filter(ExportJob.dataset == dataset)
            items = query.order_by(ExportJob.created_at.desc()).offset(offset).limit(_bounded_limit(limit)).all()
            return [_to_export_job_graph(item) for item in items]


schema = strawberry.Schema(query=Query)
