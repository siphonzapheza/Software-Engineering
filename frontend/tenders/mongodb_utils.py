"""
MongoDB utility functions for the Tender Insight Hub application.
This module provides functions to connect to MongoDB and perform CRUD operations.
"""
from pymongo import MongoClient
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def get_mongodb_client():
    """
    Get a MongoDB client connection using settings from Django settings.
    
    Returns:
        MongoClient: A MongoDB client instance
    """
    try:
        mongo_settings = settings.MONGODB_DATABASES['default']
        client = MongoClient(
            host=mongo_settings['CLIENT']['host'],
            port=mongo_settings['CLIENT']['port']
        )
        # Test connection
        client.server_info()
        logger.info("MongoDB connection established successfully")
        return client
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {str(e)}")
        raise

def get_database(db_name=None):
    """
    Get a MongoDB database instance.
    
    Args:
        db_name (str, optional): Name of the database. Defaults to the one in settings.
        
    Returns:
        Database: A MongoDB database instance
    """
    if db_name is None:
        db_name = settings.MONGODB_DATABASES['default']['NAME']
    
    client = get_mongodb_client()
    return client[db_name]

def save_to_mongodb(collection_name, data):
    """
    Save data to a MongoDB collection.
    
    Args:
        collection_name (str): Name of the collection
        data (dict or list): Data to save
        
    Returns:
        ObjectId or list: ID(s) of the inserted document(s)
    """
    db = get_database()
    collection = db[collection_name]
    
    if isinstance(data, list):
        result = collection.insert_many(data)
        return result.inserted_ids
    else:
        result = collection.insert_one(data)
        return result.inserted_id

def find_in_mongodb(collection_name, query=None, projection=None):
    """
    Find documents in a MongoDB collection.
    
    Args:
        collection_name (str): Name of the collection
        query (dict, optional): Query filter. Defaults to None.
        projection (dict, optional): Fields to include/exclude. Defaults to None.
        
    Returns:
        Cursor: MongoDB cursor with the query results
    """
    db = get_database()
    collection = db[collection_name]
    
    if query is None:
        query = {}
    
    return collection.find(query, projection)