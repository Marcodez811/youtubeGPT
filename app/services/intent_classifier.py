from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
import os
from dotenv import load_dotenv

load_dotenv()

# --- Intent Definitions ---
INTENT_DEFINITIONS = {
    "summarization": "User wants a summary, overview, TL;DR, gist, or key points of the video content.",
    "question-answering": "User is asking a specific question about the video content that requires finding an answer within the text (using RAG).",
    "flashcard-gen": "User wants to generate flashcards based on the video content.",
    "quiz-gen": "User wants to generate a quiz or test questions based on the video content.",
    "irrelevant": "User's query is completely off-topic, nonsensical, inappropriate, or unrelated to the video content *and* the ongoing conversation flow." # Refined irrelevant
}
VALID_INTENTS = list(INTENT_DEFINITIONS.keys())

# --- Classification Template --- (from step 2)
ic_template = """
You are an expert intent classification system. Your task is to categorize the user's query into ONE of the predefined intents based on its meaning and goal.

Available Intents and Descriptions:
{intent_definitions_str}

User Query:
{user_query}

Instructions:
1. Analyze the "User Query" carefully.
2. Determine which single intent from the "Available Intents" list best represents the user's primary goal.
3. Consider the descriptions provided for each intent.
4. Output *only* the exact name of the chosen intent (e.g., "summarization", "question-answering", "irrelevant").
5. Do not add any explanation, preamble, or other text. Just the intent name.

Chosen Intent:
"""

# --- LLM Initialization ---
# Use a fast model, temperature 0 for deterministic classification
llm_classifier = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    temperature=0.0,
    timeout=None,
    max_retries=2,
    api_key=os.getenv('GOOGLE_API_KEY')
)

# --- Create Prompt Template ---
prompt_template_ic = ChatPromptTemplate.from_template(ic_template)

# --- Function to Classify Intent ---
def classify_intent(user_query: str) -> str | None:
    """
    Classifies the user query into one of the predefined intents.

    Args:
        user_query: The user's input query.

    Returns:
        The classified intent name as a string, or None if classification fails
        or returns an invalid intent.
    """
    if not user_query:
        return "irrelevant" # Handle empty query

    # Format intent definitions for the prompt
    intent_defs_formatted = "\n".join(f"- {name}: {desc}" for name, desc in INTENT_DEFINITIONS.items())

    # Create the prompt
    prompt = prompt_template_ic.invoke({
        "intent_definitions_str": intent_defs_formatted,
        "user_query": user_query
    })

    try:
        # print(f"\n--- Invoking Classifier for: '{user_query}' ---") # Debugging
        # print(f"Prompt:\n{prompt.to_string()}") # Debugging
        result = llm_classifier.invoke(prompt)
        classified_intent = result.content.strip()
        # print(f"Raw LLM Output: '{classified_intent}'") # Debugging

        # Validate the output
        if classified_intent in VALID_INTENTS:
            return classified_intent
        else:
            print(f"Warning: LLM returned an invalid intent '{classified_intent}'. Defaulting to 'irrelevant'.")
            # Fallback strategy: maybe try again, or default to irrelevant/QA
            return "irrelevant"

    except Exception as e:
        print(f"\n--- Error during Intent Classification ---")
        print(f"An error occurred for query '{user_query}': {e}")
        return None # Indicate failure