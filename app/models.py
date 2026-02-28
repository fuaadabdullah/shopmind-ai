"""
Database models for ShopMindAI.

Contains models for tracking diagnostic history and root cause confirmations.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, Text, Index, JSON
from sqlalchemy.sql import func

from .database import Base


class RootCause(Base):
    """
    Track confirmed root causes for historical success rate calculation.
    
    This model stores diagnostic outcomes to enable the scoring engine to
    learn from historical data and improve ranking accuracy over time.
    """
    
    __tablename__ = "root_causes"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Vehicle identification
    make = Column(String(50), nullable=False, index=True)
    model = Column(String(50), nullable=False, index=True)
    year = Column(String(4), nullable=False, index=True)
    
    # Symptom tracking (hashed for deduplication)
    symptom_hash = Column(String(64), nullable=False, index=True)
    symptom_text = Column(Text, nullable=False)
    
    # Diagnostic result
    cause = Column(String(255), nullable=False, index=True)
    confirmed_cause = Column(String(255), nullable=False)
    
    # OBD codes involved
    obd_codes = Column(Text, nullable=True)  # Comma-separated
    
    # Source type (tsb, manual, etc.)
    source_type = Column(String(50), nullable=True)
    
    # Confidence and verification
    initial_confidence = Column(Float, nullable=True)  # 0-100
    final_confidence = Column(Float, nullable=True)   # 0-100 after confirmation
    confirmed = Column(Boolean, default=False, index=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Additional metadata
    notes = Column(Text, nullable=True)
    
    # Composite indexes for common query patterns
    __table_args__ = (
        Index('idx_vehicle_symptom', 'make', 'model', 'year', 'symptom_hash'),
        Index('idx_cause_confirmation', 'make', 'model', 'year', 'confirmed_cause'),
    )
    
    def __repr__(self):
        return f"<RootCause(id={self.id}, make={self.make}, model={self.model}, year={self.year}, cause={self.cause})>"


class DiagnosticSession(Base):
    """
    Track diagnostic sessions for analytics and improvement.
    
    Stores complete diagnostic requests and outcomes for later analysis.
    """
    
    __tablename__ = "diagnostic_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Request details
    vin = Column(String(17), nullable=False, index=True)
    symptoms = Column(Text, nullable=False)
    obd_codes = Column(Text, nullable=True)
    
    # Vehicle info (denormalized for easier querying)
    make = Column(String(50), nullable=True, index=True)
    model = Column(String(50), nullable=True, index=True)
    year = Column(String(4), nullable=True, index=True)
    
    # Results
    top_cause = Column(String(255), nullable=True)
    confidence_score = Column(Float, nullable=True)
    repair_outcome = Column(String(50), nullable=True)  # success, failure, unknown
    
    # ML predictions (Torch classifier)
    torch_predictions = Column(JSON, nullable=True)  # {cause: probability, ...}
    predicted_causes = Column(JSON, nullable=True)  # Initial predictions (before feedback)
    
    # Repair outcome tracking (for training data)
    confirmed_cause = Column(String(255), nullable=True)  # Actual repair diagnosis
    repair_parts = Column(Text, nullable=True)  # Replaced/repaired parts (comma-separated)
    training_ready = Column(Boolean, default=False, index=True)  # Ready for retraining
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Feedback
    user_feedback = Column(Text, nullable=True)
    rating = Column(Integer, nullable=True)  # 1-5
    
    def __repr__(self):
        return f"<DiagnosticSession(id={self.id}, vin={self.vin}, top_cause={self.top_cause})>"
