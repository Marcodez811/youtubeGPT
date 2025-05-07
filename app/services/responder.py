from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from app.db.life_span import shared_resources
from typing import AsyncGenerator, AsyncIterable # Import async generator type
import os
from dotenv import load_dotenv
import asyncio

load_dotenv()

async def generate_qa_response(query: str, vid_id: str):
    qa_template = """
    You are an AI tutor assisting a student with their learning experience. Your task is to provide helpful, accurate, and engaging responses based on the student's latest input, previous conversation, and retrieved knowledge.

    Context:
    - User's Last Message: {user_query}

    Retrieved Knowledge from our database:
    {retrieved_knowledge}

    Instructions for Response:
    1. Use the latest user message and recent context to understand the student's current question or difficulty.
    2. Ensure the tone is friendly, supportive, and instructional. Aim to encourage learning and understanding.

    Your response should incorporate the key information from the context and retrievals to answer the student's query concisely and clearly.
    If the user asks something about what isn't present in the video, simply tell him the video does not provide any insights on the topic he/she's speaking about, and that he/she should look for other videos.
    --- 

    Response: 
    """
    vector_store = shared_resources.get("vector_store")
    results = vector_store.similarity_search(query=query, vid_id=vid_id)
    retrieved_chunks = [str(r['text']) for r in results]

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        temperature=1.0,
        max_tokens=None,
        timeout=None,
        max_retries=2,
        api_key=os.getenv('GOOGLE_API_KEY')
    )
    prompt_template = ChatPromptTemplate.from_template(qa_template)
    prompt = prompt_template.invoke({
            "user_query": query,
            "retrieved_knowledge": str("\n-".join(retrieved_chunks)),
        })

    try:
        print("\n--- Invoking LLM Stream---")
        async for chunk in llm.astream(prompt):
            # chunk is typically an AIMessageChunk or similar object
            content = chunk.content
            if content: # Ensure content exists before yielding
                yield content
        print("\n--- LLM Response Completed---")
    except Exception as e:
        print(f"\n--- Error during LLM Invocation ---")
        print(f"An error occurred: {e}")
        yield f"\nAn error occurred while generating the response: {e}"


async def generate_summary_response(transcript: str, query: str):
    template_adaptive_summary = """
    You are an AI assistant specializing in summarizing text based on specific user requests.

    Video Content:
    {transcript}

    User's Summarization Request:
    {user_query}

    Task:
    Generate a summary or response based on the "Video Content" that directly addresses the "User's Summarization Request".

    Guidelines:
    1. Carefully read the "Video Content".
    2. Understand the specific focus or type of summary requested in the "User's Summarization Request" (e.g., key takeaways, specific reasons, highlights, TL;DR, general overview).
    3. Extract the most relevant information from the video to fulfill this specific request.
    4. Synthesize this information into a coherent response that directly answers the user's request.
    5. Ensure the response is concise, accurate, and based *only* on the provided video transcript. Do not add external information.
    6. If the request is very general (like "summarize this"), provide a balanced summary of the main points.
    7. Match the tone of the response to the request (e.g., a TL;DR should be very brief).

    ---

    Response:
    """

    user_query = query

    # Initialize the LLM (adjust model name if needed)
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-pro-exp-03-25",
        temperature=0.5,
        max_tokens=None,
        timeout=None,
        max_retries=2,
        api_key=os.getenv('GOOGLE_API_KEY')
    )

    # Create the prompt template from the adaptive template string
    prompt_template = ChatPromptTemplate.from_template(template_adaptive_summary)

    # Invoke the template with BOTH the transcript and the specific user query
    prompt = prompt_template.invoke({
            "transcript": transcript, # Pass the full transcript text
            "user_query": user_query          # Pass the specific user request
        })

    try:
        print("\n--- Invoking LLM Stream---")
        async for chunk in llm.astream(prompt):
            content = chunk.content
            if content:
                yield content
        print("\n--- LLM Response Completed---")
    except Exception as e:
        print(f"\n--- Error during LLM Invocation ---")
        print(f"An error occurred: {e}")
        yield f"\nAn error occurred while generating the response: {e}"