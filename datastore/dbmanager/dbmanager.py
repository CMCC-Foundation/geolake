from __future__ import annotations

import os
import yaml
import logging
import uuid
import secrets
from datetime import datetime
from enum import auto, Enum as Enum_, unique

from sqlalchemy import (
    Column,
    create_engine,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    JSON,
    Sequence,
    String,
    Table,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

from .singleton import Singleton


def is_true(item) -> bool:
    """If `item` represents `True` value"""
    if isinstance(item, str):
        return item.lower() in ["y", "yes", "true", "t"]
    return bool(item)


def generate_key() -> str:
    """Generate as new api key for a user"""
    return secrets.token_urlsafe(nbytes=32)


@unique
class RequestStatus(Enum_):
    """Status of the Request"""

    PENDING = auto()
    QUEUED = auto()
    RUNNING = auto()
    DONE = auto()
    FAILED = auto()
    TIMEOUT = auto()

    @classmethod
    def _missing_(cls, value):
        return cls.PENDING


class _Repr:
    def __repr__(self):
        cols = self.__table__.columns.keys()  # pylint: disable=no-member
        kwa = ", ".join(f"{col}={getattr(self, col)}" for col in cols)
        return f"{type(self).__name__}({kwa})"


Base = declarative_base(cls=_Repr, name="Base")


association_table = Table(
    "users_roles",
    Base.metadata,
    Column("user_id", ForeignKey("users.user_id")),
    Column("role_id", ForeignKey("roles.role_id")),
)


class Role(Base):
    __tablename__ = "roles"
    role_id = Column(Integer, Sequence("role_id_seq"), primary_key=True)
    role_name = Column(String(255), nullable=False, unique=True)


class User(Base):
    __tablename__ = "users"
    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # keycloak_id = Column(UUID(as_uuid=True), nullable=False, unique=True, default=uuid.uuid4)
    api_key = Column(
        String(255), nullable=False, unique=True, default=generate_key
    )
    contact_name = Column(String(255))
    requests = relationship("Request", lazy="dynamic")
    roles = relationship("Role", secondary=association_table, lazy="selectin")


class Worker(Base):
    __tablename__ = "workers"
    worker_id = Column(Integer, primary_key=True)
    status = Column(String(255), nullable=False)
    host = Column(String(255))
    dask_scheduler_port = Column(Integer)
    dask_dashboard_address = Column(String(10))
    created_on = Column(DateTime, default=datetime.now)


class Request(Base):
    __tablename__ = "requests"
    request_id = Column(Integer, primary_key=True)
    status = Column(Enum(RequestStatus), nullable=False)
    priority = Column(Integer)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False
    )
    worker_id = Column(Integer, ForeignKey("workers.worker_id"))
    dataset = Column(String(255))
    product = Column(String(255))
    query = Column(JSON())
    estimate_size_bytes = Column(Integer)
    created_on = Column(DateTime, default=datetime.now)
    last_update = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    fail_reason = Column(String(1000))
    download = relationship("Download", uselist=False, lazy="selectin")


class Download(Base):
    __tablename__ = "downloads"
    download_id = Column(Integer, primary_key=True)
    download_uri = Column(String(255))
    request_id = Column(
        Integer, ForeignKey("requests.request_id"), nullable=False
    )
    storage_id = Column(Integer, ForeignKey("storages.storage_id"))
    location_path = Column(String(255))
    size_bytes = Column(Integer)
    created_on = Column(DateTime, default=datetime.now)


class Storage(Base):
    __tablename__ = "storages"
    storage_id = Column(Integer, primary_key=True)
    name = Column(String(255))
    host = Column(String(20))
    protocol = Column(String(10))
    port = Column(Integer)


class DBManager(metaclass=Singleton):
    _LOG = logging.getLogger("geokube.DBManager")

    def __init__(self) -> None:
        for venv_key in [
            "POSTGRES_DB",
            "POSTGRES_USER",
            "POSTGRES_PASSWORD",
            "DB_SERVICE_PORT",
        ]:
            self._LOG.info(
                "attempt to load data from environment variable: `%s`",
                venv_key,
            )
            if venv_key not in os.environ:
                self._LOG.error(
                    "missing required environment variable: `%s`", venv_key
                )
                raise KeyError(
                    f"missing required environment variable: {venv_key}"
                )

        user = os.environ["POSTGRES_USER"]
        password = os.environ["POSTGRES_PASSWORD"]
        host = os.environ["DB_SERVICE_HOST"]
        port = os.environ["DB_SERVICE_PORT"]
        database = os.environ["POSTGRES_DB"]

        url = f"postgresql://{user}:{password}@{host}:{port}/{database}"
        self._LOG.info("db connection: `%s`", url)
        self.__engine = create_engine(
            url, echo=is_true(os.environ.get("DB_LOGGING", False))
        )
        self.__session_maker = sessionmaker(bind=self.__engine)

    def _create_database(self):
        try:
            Base.metadata.create_all(self.__engine)
        except Exception as exception:
            self._LOG.error(
                "could not create a database due to an error", exc_info=True
            )
            raise exception

    def add_user(
        self,
        contact_name: str,
        user_id: UUID | None = None,
        api_key: str | None = None,
        roles_names: list[str] | None = None,
    ):
        with self.__session_maker() as session:
            user = User(
                user_id=user_id, api_key=api_key, contact_name=contact_name
            )
            if roles_names:
                user.roles.extend([
                    session.query(Role)
                    .where(Role.role_name == role_name)
                    .all()[0]  # NOTE: role_name is unique in the database
                    for role_name in roles_names
                ])
            session.add(user)
            session.commit()
            return user

    def get_user_details(self, user_id: int):
        with self.__session_maker() as session:
            return session.query(User).get(user_id)

    def get_user_roles_names(self, user_id: int | None = None) -> list[str]:
        if user_id is None:
            return ["public"]
        with self.__session_maker() as session:
            return list(
                map(
                    lambda role: role.role_name,
                    session.query(User).get(user_id).roles,
                )
            )

    def get_request_details(self, request_id: int):
        with self.__session_maker() as session:
            return session.query(Request).get(request_id)

    def get_download_details_for_request(self, request_id: int):
        with self.__session_maker() as session:
            request_details = session.query(Request).get(request_id)
            if request_details is None:
                raise ValueError(
                    f"Request with id: {request_id} doesn't exist"
                )
            return request_details.download

    def create_request(
        self,
        user_id: int = 1,
        dataset: str | None = None,
        product: str | None = None,
        query: str | None = None,
        worker_id: int | None = None,
        priority: str | None = None,
        estimate_size_bytes: int | None = None,
        status: RequestStatus = RequestStatus.PENDING,
    ) -> int:
        # TODO: Add more request-related parameters to this method.
        with self.__session_maker() as session:
            request = Request(
                status=status,
                priority=priority,
                user_id=user_id,
                worker_id=worker_id,
                dataset=dataset,
                product=product,
                query=query,
                estimate_size_bytes=estimate_size_bytes,
                created_on=datetime.utcnow(),
            )
            session.add(request)
            session.commit()
            return request.request_id

    def update_request(
        self,
        request_id: int,
        worker_id: int | None = None,
        status: RequestStatus | None = None,
        location_path: str = None,
        size_bytes: int = None,
        fail_reason: str = None,
    ) -> int:
        with self.__session_maker() as session:
            request = session.query(Request).get(request_id)
            if status:
                request.status = status
            if worker_id:
                request.worker_id = worker_id
            request.last_update = datetime.utcnow()
            request.fail_reason = fail_reason
            session.commit()
            if status is RequestStatus.DONE:
                download = Download(
                    location_path=location_path,
                    storage_id=0,
                    request_id=request.request_id,
                    created_on=datetime.utcnow(),
                    download_uri=f"/download/{request_id}",
                    size_bytes=size_bytes,
                )
                session.add(download)
                session.commit()
            return request.request_id

    def get_request_status_and_reason(
        self, request_id
    ) -> None | RequestStatus:
        with self.__session_maker() as session:
            if request := session.query(Request).get(request_id):
                return RequestStatus(request.status), request.fail_reason
            raise IndexError(
                f"Request with id: `{request_id}` does not exist!"
            )

    def get_requests_for_user_id(self, user_id) -> list[Request]:
        with self.__session_maker() as session:
            return session.query(User).get(user_id).requests.all()

    def get_requests_for_user_id_and_status(
        self, user_id, status: RequestStatus | tuple[RequestStatus]
    ) -> list[Request]:
        if isinstance(status, RequestStatus):
            status = (status,)
        with self.__session_maker() as session:
            return session.get(User, user_id).requests.filter(
                Request.status.in_(status)
            )

    def get_download_details_for_request_id(self, request_id) -> Download:
        with self.__session_maker() as session:
            request_details = session.query(Request).get(request_id)
            if request_details is None:
                raise IndexError(
                    f"Request with id: `{request_id}` does not exist!"
                )
            return request_details.download

    def create_worker(
        self,
        status: str,
        dask_scheduler_port: int,
        dask_dashboard_address: int,
        host: str = "localhost",
    ) -> int:
        with self.__session_maker() as session:
            worker = Worker(
                status=status,
                host=host,
                dask_scheduler_port=dask_scheduler_port,
                dask_dashboard_address=dask_dashboard_address,
                created_on=datetime.utcnow(),
            )
            session.add(worker)
            session.commit()
            return worker.worker_id
