import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
import numpy as np
import shutil
import tempfile
from pathlib import Path


# Create a minimal app for testing that doesn't use static files mount
# This avoids the issue where static files catch all routes
@pytest.fixture
def app_without_static():
    """Create app without static files mount for testing."""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    from app.retriever import retrieve
    from app.ranker import rank_diagnostics
    
    test_app = FastAPI()
    
    test_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    class DiagnosticRequest(BaseModel):
        vin: str
        obdcodes: str
        symptoms: str
    
    @test_app.get("/health")
    def health_check():
        return {"status": "healthy"}
    
    @test_app.post("/diagnose")
    def diagnose(req: DiagnosticRequest):
        retrieved = retrieve(req.symptoms + " " + req.obdcodes)
        ranked = rank_diagnostics(req.symptoms, retrieved)
        return {"result": ranked}
    
    return test_app


@pytest.fixture
def client(app_without_static):
    """FastAPI test client fixture."""
    return TestClient(app_without_static)


@pytest.fixture
def mock_provider():
    """Mock AI provider for testing."""
    with patch('app.ranker.get_provider') as mock:
        provider = MagicMock()
        provider.generate.return_value = "Test response from AI provider"
        mock.return_value = provider
        yield provider


@pytest.fixture
def mock_embeddings():
    """Mock embeddings for testing."""
    with patch('app.retriever.embed_text') as mock:
        mock.return_value = [np.random.rand(384).tolist()]
        yield mock


@pytest.fixture
def mock_vector_store():
    """Mock vector store search for testing."""
    with patch('app.retriever.search') as mock:
        mock.return_value = [
            {
                "cause": "Battery Issues",
                "description": "The battery may be dead or dying",
                "symptoms": ["car won't start", "lights dim"],
                "tests": ["voltage test", "load test"],
                "labor_hours": 0.5
            },
            {
                "cause": "Starter Motor Failure",
                "description": "The starter motor may be faulty",
                "symptoms": ["clicking sound", "no crank"],
                "tests": ["starter test", "voltage drop test"],
                "labor_hours": 1.5
            }
        ]
        yield mock


@pytest.fixture
def sample_diagnostic_request():
    """Sample diagnostic request payload."""
    return {
        "vin": "1HGBH41JXMN109186",
        "obdcodes": "P0420",
        "symptoms": "car won't start, clicking sound"
    }


@pytest.fixture
def sample_retrieved_docs():
    """Sample retrieved documents for testing."""
    return [
        {
            "cause": "Battery Issues",
            "description": "The battery may be dead or dying",
            "symptoms": ["car won't start", "lights dim"],
            "tests": ["voltage test", "load test"],
            "labor_hours": 0.5
        },
        {
            "cause": "Starter Motor Failure",
            "description": "The starter motor may be faulty",
            "symptoms": ["clicking sound", "no crank"],
            "tests": ["starter test", "voltage drop test"],
            "labor_hours": 1.5
        }
    ]


@pytest.fixture
def sample_embedding():
    """Sample embedding vector for testing."""
    return np.random.rand(384).tolist()


@pytest.fixture
def test_faiss_index():
    """Create a temporary copy of test FAISS index for E2E tests.
    
    This fixture copies the pre-built test index to a temporary directory
    and yields a VectorStore instance pointing to it. Cleans up after test.
    """
    from app.vector_store import VectorStore
    
    # Path to test fixtures
    fixtures_dir = Path(__file__).parent / "fixtures" / "test_faiss_index"
    index_file = fixtures_dir / "index.bin"
    meta_file = fixtures_dir / "meta.pkl"
    
    # Ensure test index exists
    if not index_file.exists() or not meta_file.exists():
        pytest.skip(
            "Test FAISS index not found. "
            "Run 'python tests/fixtures/build_test_faiss_index.py' first."
        )
    
    # Create temp directory for this test
    temp_dir = tempfile.mkdtemp(prefix="test_faiss_")
    temp_index = Path(temp_dir) / "index.bin"
    temp_meta = Path(temp_dir) / "meta.pkl"
    
    try:
        # Copy index files to temp location
        shutil.copy(index_file, temp_index)
        shutil.copy(meta_file, temp_meta)
        
        # Patch VectorStore paths to use temp index
        with patch('app.vector_store.INDEX_PATH', str(temp_index)):
            with patch('app.vector_store.META_PATH', str(temp_meta)):
                # Reset singleton to force reload with test paths
                VectorStore._instance = None
                
                # Create VectorStore with test index
                store = VectorStore()
                
                yield store
                
                # Reset singleton after test
                VectorStore._instance = None
    finally:
        # Cleanup temp directory
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def test_db():
    """Create in-memory SQLite database for testing.
    
    This fixture creates all tables from models and yields a
    SQLAlchemy Session. Automatically cleans up after test.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker, Session
    from app.database import Base
    
    # Create in-memory SQLite engine
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        echo=False
    )
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    # Create session factory
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Create session
    db = TestingSessionLocal()
    
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


@pytest.fixture
def test_app_with_db(test_db):
    """Create FastAPI app with test database dependency override.
    
    This fixture creates a test app instance and injects the test
    database session for E2E tests that require persistence.
    """
    from fastapi import FastAPI, Depends
    from fastapi.middleware.cors import CORSMiddleware
    from app.database import get_db
    from app.routes import diagnose
    
    # Create test app
    test_app = FastAPI(title="ShopMindAI Test")
    
    test_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Override database dependency
    def override_get_db():
        try:
            yield test_db
        finally:
            pass
    
    test_app.dependency_overrides[get_db] = override_get_db
    
    # Include routes
    test_app.include_router(diagnose.router, prefix="/api", tags=["diagnostics"])
    
    return test_app


@pytest.fixture
def mock_llm_provider():
    """Mock LLM provider with contract validation for E2E tests.
    
    This fixture patches the LLM provider in ranker.py while allowing
    real embeddings and FAISS retrieval to run. Returns realistic
    diagnostic rankings without actual API calls.
    """
    from tests.mocks.llm_contract_mock import create_mock_llm_provider
    
    mock = create_mock_llm_provider()
    
    with patch('app.ranker.get_provider') as mock_get_provider:
        mock_get_provider.return_value = mock
        yield mock
