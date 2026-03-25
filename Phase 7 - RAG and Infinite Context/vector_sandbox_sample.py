import os
import chromadb
import chromadb.utils.embedding_functions as embedding_functions

# 1. API KEY CHECK
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("[ERROR] GEMINI_API_KEY not found in environment variables.")
    # For local testing only, you can hardcode it here:
    # api_key = "your_actual_api_key_here"
    exit()

def run_sandbox():
    print("1. Booting up local Vector Database...")
    # This creates an in-memory database that disappears when the script stops
    client = chromadb.Client()

    # 2. THE TRANSLATOR (Embedding Function)
    # This tells Chroma: "Whenever I give you text, use Gemini to turn it into numbers."
    google_ef = embedding_functions.GoogleGenerativeAiEmbeddingFunction(api_key=api_key)

    # 3. CREATE THE TABLE (Collection)
    print("2. Creating the 'real_estate' collection...")
    collection = client.create_collection(
        name="real_estate_listings", 
        embedding_function=google_ef
    )

    # 4. POPULATE THE DATABASE
    print("3. Generating AI Embeddings for property listings (This takes a second)...")
    
    # Notice the descriptions: None of them explicitly say "good for dogs"
    collection.add(
        documents=[
            "A sleek, modern downtown condo on the 45th floor. Floor-to-ceiling windows, minimalist design, and close to nightlife.",
            "A cozy 3-bedroom suburban family home. Features a massive, fully-fenced green lawn in the back, mature oak trees, and a quiet cul-de-sac.",
            "A cheap fixer-upper in the industrial district. Needs a new roof and plumbing. Great investment opportunity.",
            "Ultra-luxury waterfront mansion. Features a private dock, infinity pool, 12-car garage, and marble floors throughout."
        ],
        # Metadata allows us to store strict SQL-style data alongside the AI vectors
        metadatas=[
            {"price": 450000, "type": "condo"},
            {"price": 550000, "type": "house"},
            {"price": 150000, "type": "house"},
            {"price": 5200000, "type": "mansion"}
        ],
        ids=["listing_1", "listing_2", "listing_3", "listing_4"]
    )
    print("   -> Database populated successfully!\n")

    # ==========================================
    # 5. THE SEMANTIC SEARCH
    # ==========================================
    # Here is the magic. We search for a concept, not keywords.
    search_query = "I have two golden retrievers who love to run outside."
    
    print(f"USER SEARCH: \"{search_query}\"\n")
    print("4. Executing vector distance calculation...")
    
    results = collection.query(
        query_texts=[search_query],
        n_results=1 # Only give me the single best match
    )

    # 6. DISPLAY RESULTS
    best_match_id = results['ids'][0][0]
    best_match_text = results['documents'][0][0]
    best_match_metadata = results['metadatas'][0][0]
    distance_score = results['distances'][0][0]

    print("========================================")
    print("  SEARCH RESULT MATCH ")
    print("========================================")
    print(f"Property ID: {best_match_id}")
    print(f"Price: ${best_match_metadata['price']}")
    print(f"Description: {best_match_text}")
    print(f"\nVector Distance Score: {round(distance_score, 4)} (Lower is closer in meaning)")

if __name__ == "__main__":
    run_sandbox()