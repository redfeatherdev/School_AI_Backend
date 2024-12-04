import re
import json
import time
import requests
from app.config import OPENAI_API_KEY, ANTHROPIC_API_KEY, SERPAPI_API_KEY

MAX_RETRIES = 10

def send_request_with_retries(endpoint, headers, payload):
    for attempt in range(5):
        try:
            response = requests.post(endpoint, headers=headers, json=payload, stream=True)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Attempt {attempt+1} failed: {e}")
            if response:
                try:
                    print("Response Content:", response.json())
                except Exception:
                    print("Response Content (non-JSON):", response.text)
            time.sleep(5)
    raise requests.exceptions.RequestException("Failed to connect after multiple attempts.")

def send_request_with_rate_limit(endpoint, headers, payload):
    try:
        response = requests.post(endpoint, headers=headers, json=payload)
        response.raise_for_status()

        remaining = int(response.headers.get('x-ratelimit-remaining', 100))
        reset_time = int(response.headers.get('x-ratelimit-reset', 1))
        
        if remaining <= 1:
            time.sleep(reset_time)
        
        return response
    except requests.exceptions.HTTPError as e:
        if response.status_code == 429:
            reset_time = int(response.headers.get('Retry-After', 60))
            time.sleep(reset_time)
        raise e
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return None
    
def call_openai_outline_api(request_payload, chapter_count, subchapter_count):
    payload = {
        "model": "gpt-4",
        "messages": request_payload,
        "max_tokens": 2000
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }
    endpoint = "https://api.openai.com/v1/chat/completions"

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = send_request_with_retries(endpoint, headers=headers, payload=payload)

            if response and 'choices' in response:
                try:
                    gpt_response = response['choices'][0]['message']['content']
                    return parse_and_clean_response(gpt_response, chapter_count, subchapter_count)
                except KeyError as e:
                    print(f"Attempt {attempt}: KeyError while accessing the response: {e}. Full response: {response}")
                    raise ValueError("Unexpected structure in OpenAI response.")
            else:
                print(f"Attempt {attempt}: Invalid or unexpected response format: {response}")
                raise ValueError("Invalid response from OpenAI.")

        except Exception as e:
            print(f"Attempt {attempt}: OpenAI request failed with error: {e}")
            if attempt < MAX_RETRIES:
                print(f"Retrying... ({attempt}/{MAX_RETRIES})")
                time.sleep(2)
            else:
                print(f"Max retries reached. Failing after {MAX_RETRIES} attempts.")
                raise ValueError("All retry attempts failed.")
    
def call_anthropic_outline_api(prompt, chapter_count, subchapter_count):
    instruction = f"""
    Generate a comprehensive list of chapters and subchapters for a detailed course on {prompt}.
    The number of chapters is {chapter_count}, and each chapter has {subchapter_count} subchapters.
    Provide the structured JSON format with no extraneous information.
    """
    instruction = instruction.strip()

    headers = {
        "Content-Type": "application/json",
        "x-api-key": ANTHROPIC_API_KEY
    }
    payload = {
        "model": "claude-v1",
        "prompt": instruction,
        "max_tokens": 2000,
        "temperature": 0.5
    }
    endpoint = "https://api.anthropic.com/v1/complete"

    response = send_request_with_retries(endpoint, headers=headers, payload=payload)
    if response.status_code == 400:
        print(f"Bad Request: {response.text}")
        raise ValueError(f"Bad request sent to Anthropic. Response: {response.text}")
    anth_response = response.json().get('completion', '')

    return parse_and_clean_response(anth_response, chapter_count, subchapter_count)

def parse_and_clean_response(response_content, chapter_count, subchapter_count):
    try:
        json_response = json.loads(response_content)
        
        if not isinstance(json_response, dict):
            raise ValueError("Invalid response format.")
        
        for chapter, subchapters in json_response.items():
            if isinstance(subchapters, list):
                json_response[chapter] = [subchapter.split(": ", 1)[-1] for subchapter in subchapters]
            else:
                raise ValueError(f"Subchapters for {chapter} are not in list format")
        
        if len(json_response) != chapter_count:
            raise ValueError(f"Expected {chapter_count} chapters but received {len(json_response)}.")
        
        for chapter, subchapters in json_response.items():
            if len(subchapters) != subchapter_count:
                raise ValueError(f"Expected {subchapter_count} subchapters in {chapter}, but got {len(subchapters)}.")
        
        sorted_chapters = dict(sorted(json_response.items(), key=lambda item: int(item[0].split(' ')[1].strip(':'))))
        return sorted_chapters

    except (json.JSONDecodeError, ValueError) as e:
        print(f"Failed to decode or validate JSON response: {e}")
        raise

def fetch_content(prompt, chapterName, subchapterName, include_images):
    prompt_message = f"""
    You are an expert content generator for a technical course. Your task is to create a detailed, rich guide that resembles popular tutorials found online. 
    The content should be highly informative, but **should not** include any references to chapter or subchapter titles, such as "Chapter 1" or "Subchapter: Overview". Focus purely on delivering educational content that flows naturally.

    The content should flow naturally with the following sections:
    - Introduction: Start with a brief, engaging introduction.
    - Key Concepts: Explain the key concepts in a clear and concise manner, ideally in a bulleted list or short paragraphs.
    - Example Code: Include relevant code examples formatted in markdown where applicable.
    - Step-by-Step Instructions: For complex topics, provide step-by-step guidance.
    - External Resources: List external resources in the following markdown format:
        - [Resource Name](https://example.com)

    Do not include chapter or subchapter names like "{chapterName}" or "{subchapterName}" in the response. Focus on delivering content that explains the course topic: '{prompt}'.
    """

    if include_images:
        prompt_message += "\nAdditionally, provide relevant image descriptions as needed."

    request_payload = [
        {"role": "system", "content": "You are an expert content writer for technical courses."},
        {"role": "user", "content": prompt_message}
    ]
    
    payload = {
        "model": "gpt-4",
        "messages": request_payload,
        "max_tokens": 4000
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }
    endpoint = "https://api.openai.com/v1/chat/completions"
    
    response = send_request_with_rate_limit(endpoint, headers, payload)
    
    if response and response.status_code == 200:
        gpt_response = response.json().get('choices', [])[0].get('message', {}).get('content', '')

        if gpt_response:
            image_descriptions = generate_image_descriptions(gpt_response)

            return gpt_response.strip(), image_descriptions
        else:
            print("No valid content generated.")
            return None
    else:
        print(f"Error in response: {response.text}")
        return None

def generate_image_descriptions(gpt_response):
    """
    Generate generic image descriptions if GPT does not provide them.
    For example, if the content contains a section for 'Introduction' or 'Key Concepts',
    create default image descriptions for those sections.
    """
    descriptions = []
    
    if "Introduction" in gpt_response:
        descriptions.append("An illustrative diagram introducing the concept.")
    
    if "Key Concepts" in gpt_response:
        descriptions.append("A diagram explaining key concepts in the content.")
    
    return descriptions[:2]

def fetch_images_for_content(gpt_response):
    image_descriptions = extract_image_suggestions(gpt_response)
    image_urls = [search_image(desc)[0] for desc in image_descriptions if desc]
    return image_urls

def insert_images_into_content(content, image_descriptions, image_urls):
    """
    Insert image URLs into the content based on the section that matches the image descriptions.
    """
    for desc, url in zip(image_descriptions, image_urls):
        if "Introduction" in content and "introducing the concept" in desc:
            content = content.replace("Introduction", f"Introduction\n![{desc}]({url})", 1)
        elif "Key Concepts" in content and "key concepts" in desc:
            content = content.replace("Key Concepts", f"Key Concepts\n![{desc}]({url})", 1)
    
    print("Content with Images:", content)
    return content

def extract_image_suggestions(gpt_response):
    return re.findall(r'\[IMAGE:\s*(.*?)\]', gpt_response)

def search_image(query, num_images=1):
    try:
        params = {
            "engine": "google_images",
            "q": query,
            "api_key": SERPAPI_API_KEY,
            "num": num_images
        }
        response = requests.get("https://serpapi.com/search", params=params)
        response.raise_for_status()

        images = response.json().get('images_results', [])
        return [img.get('original', None) for img in images if img.get('original')]
    
    except requests.exceptions.RequestException as e:
        print(f"Error fetching images: {e}")
        return []