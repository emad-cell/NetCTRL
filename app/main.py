from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html
from app.db.database import Base, engine
from app.routers import auth, config, devices

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="NetCTRL API",
    description="Web-based network device management platform",
    version="0.1.0",
    redoc_url=None,  # disable default so we add it manually below
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(devices.router)
app.include_router(config.router)

# Manually serve ReDoc with a pinned CDN version — fixes the blank page issue
@app.get("/redoc", include_in_schema=False)
async def redoc_html():
    return get_redoc_html(
        openapi_url="/openapi.json",
        title="NetCTRL API Docs",
        redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@2.1.3/bundles/redoc.standalone.js",
    )

@app.get("/")
def root():
    return {"message": "NetCTRL API is running"}
