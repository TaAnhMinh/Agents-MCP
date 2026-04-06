import os
import chromadb
import chromadb.utils.embedding_functions as embedding_functions

class PropertyDatabase:
    """Handles all Vector Database operations and AI Embeddings."""
    
    def __init__(self):
        # 1. Validate API Key
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set!")

        # 2. Boot up ChromaDB
        self.client = chromadb.Client()
        self.google_ef = embedding_functions.GoogleGenerativeAiEmbeddingFunction(api_key=self.api_key)
        
        # 3. Create the collection
        self.collection = self.client.create_collection(
            name="real_estate_listings", 
            embedding_function=self.google_ef
        )
        
        # 4. Populate it immediately upon creation
        self._populate_database()

    def _populate_database(self):
        """Internal method to load the fake listings into memory."""
        self.collection.add(
            documents=[
                "A sleek, modern downtown condo on the 45th floor. Floor-to-ceiling windows, minimalist design, and close to nightlife.",
                "A cozy 3-bedroom suburban family home. Features a massive, fully-fenced green lawn in the back, mature oak trees, and a quiet cul-de-sac.",
                "A cheap fixer-upper in the industrial district. Needs a new roof and plumbing. Great investment opportunity.",
                "Ultra-luxury waterfront mansion. Features a private dock, infinity pool, 12-car garage, and marble floors throughout."
            ],
            metadatas=[
                {"price": 450000, "type": "condo"},
                {"price": 550000, "type": "house"},
                {"price": 150000, "type": "house"},
                {"price": 5200000, "type": "mansion"}
            ],
            ids=["listing_1", "listing_2", "listing_3", "listing_4"]
        )

    def search_properties(self, search_query: str, excluded_ids: list[str] = None) -> str:
        if excluded_ids is None:
            excluded_ids = []
            
        # DYNAMIC N: Always fetch exactly 1 more than the number of excluded IDs
        dynamic_n = len(excluded_ids) + 1 
        
        results = self.collection.query(
            query_texts=[search_query],
            n_results=dynamic_n
        )
        
        if not results['ids'][0]:
            return "No matching properties found in the database."
            
        # Loop through the dynamic results and find the one that isn't on the blacklist
        for i in range(len(results['ids'][0])):
            match_id = results['ids'][0][i]
            
            if match_id not in excluded_ids:
                best_match_text = results['documents'][0][i]
                best_match_price = results['metadatas'][0][i]['price']
                return f"Match Found! Property ID: {match_id}. Price: ${best_match_price}. Description: {best_match_text}"
                
        return "No other matching properties found."