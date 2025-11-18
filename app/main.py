from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
from .routers import central_rules, departments, intent, workpal


def create_app() -> FastAPI:
    Base.metadata.create_all(bind=engine)

    app = FastAPI(title="WorkPal Backend")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(departments.router)
    app.include_router(central_rules.router)
    app.include_router(intent.router)
    app.include_router(workpal.router)

    return app


app = create_app()
