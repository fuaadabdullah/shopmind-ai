"""
Query utilities for parameterized database access.

Provides defensive wrappers around SQLAlchemy ORM to ensure all queries
use parameterized statements and prevent SQL injection attacks.

All user-provided input is bound as parameters, never interpolated into SQL strings.
"""
from typing import Any, TypeVar, Generic, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

T = TypeVar('T')


class SafeQuery(Generic[T]):
    """
    Wrapper for safe parameterized queries.
    
    Enforces that all filters use SQLAlchemy column comparisons
    (which are automatically parameterized) rather than string
    interpolation or concatenation.
    """
    
    def __init__(self, session: Session, model: type[T]):
        """
        Initialize safe query builder.
        
        Args:
            session: SQLAlchemy database session
            model: Model class to query
        """
        self.session = session
        self.model = model
        self._query = session.query(model)
    
    def filter_by_id(self, record_id: int) -> Optional[T]:
        """
        Safe filter by primary key (parameterized).
        
        Args:
            record_id: Primary key value (must be int)
            
        Returns:
            First matching record or None
        """
        if not isinstance(record_id, int):
            raise TypeError(f"Expected int for record_id, got {type(record_id)}")
        
        return self._query.filter(self.model.id == record_id).first()
    
    def filter_by_boolean(self, column_name: str, value: bool) -> list[T]:
        """
        Safe filter by boolean column (parameterized).
        
        Args:
            column_name: Column attribute name (must exist on model)
            value: Boolean value to filter
            
        Returns:
            List of matching records
            
        Raises:
            AttributeError: If column doesn't exist on model
        """
        if not hasattr(self.model, column_name):
            raise AttributeError(
                f"Model {self.model.__name__} has no column '{column_name}'"
            )
        
        column = getattr(self.model, column_name)
        return self._query.filter(column == value).all()
    
    def filter_by_string(self, column_name: str, value: str) -> list[T]:
        """
        Safe filter by string column (parameterized).
        
        Args:
            column_name: Column attribute name
            value: String value to filter (parameterized)
            
        Returns:
            List of matching records
            
        Raises:
            AttributeError: If column doesn't exist
            TypeError: If value is not string
        """
        if not isinstance(value, str):
            raise TypeError(f"Expected str for value, got {type(value)}")
        
        if not hasattr(self.model, column_name):
            raise AttributeError(
                f"Model {self.model.__name__} has no column '{column_name}'"
            )
        
        column = getattr(self.model, column_name)
        return self._query.filter(column == value).all()
    
    def filter_not_null(self, column_name: str) -> list[T]:
        """
        Safe filter for NOT NULL values.
        
        Args:
            column_name: Column attribute name
            
        Returns:
            List of records where column is not null
            
        Raises:
            AttributeError: If column doesn't exist
        """
        if not hasattr(self.model, column_name):
            raise AttributeError(
                f"Model {self.model.__name__} has no column '{column_name}'"
            )
        
        column = getattr(self.model, column_name)
        return self._query.filter(column.isnot(None)).all()
    
    def count(self) -> int:
        """
        Count matching records.
        
        Returns:
            Count of records
        """
        return self._query.count()
    
    def all(self) -> list[T]:
        """
        Fetch all records.
        
        Returns:
            List of all records
        """
        return self._query.all()
    
    def first(self) -> Optional[T]:
        """
        Fetch first record.
        
        Returns:
            First record or None
        """
        return self._query.first()


def validate_column_name(model: type[T], column_name: str) -> str:
    """
    Validate that a column name exists on a model.
    
    Args:
        model: SQLAlchemy model class
        column_name: Column name to validate
        
    Returns:
        The column name (for chaining)
        
    Raises:
        AttributeError: If column doesn't exist
    """
    if not hasattr(model, column_name):
        raise AttributeError(
            f"Model {model.__name__} has no column '{column_name}'"
        )
    return column_name


def validate_int_id(value: Any) -> int:
    """
    Validate and convert value to integer ID.
    
    Args:
        value: Value to validate
        
    Returns:
        Integer value
        
    Raises:
        TypeError: If value cannot be converted to int
        ValueError: If value is <= 0
    """
    try:
        int_value = int(value)
    except (TypeError, ValueError) as e:
        raise TypeError(f"Invalid ID value: {value}") from e
    
    if int_value <= 0:
        raise ValueError(f"ID must be positive, got {int_value}")
    
    return int_value


def validate_non_empty_string(value: Any, field_name: str = "value") -> str:
    """
    Validate that value is a non-empty string.
    
    Args:
        value: Value to validate
        field_name: Name of field for error messages
        
    Returns:
        The validated string
        
    Raises:
        TypeError: If not a string
        ValueError: If empty string
    """
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be string, got {type(value)}")
    
    if not value.strip():
        raise ValueError(f"{field_name} cannot be empty")
    
    return value.strip()
