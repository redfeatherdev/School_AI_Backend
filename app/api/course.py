from flask import request, jsonify
from flask_socketio import SocketIO
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, UTC

from app import app, db
from app.models.course import Course
from app.utils.course import call_openai_outline_api, call_anthropic_outline_api, fetch_content, fetch_images_for_content, insert_images_into_content

socketio = SocketIO(app, cors_allowed_origins="*")

@app.route("/api/v1/course/generate-outline", methods=["POST"])
def generate_outline():
    data = request.get_json()
    prompt = data.get('prompt')
    chapter_count = data.get('chapterCount')
    subchapter_count = data.get('subchapterCount')

    instruction = f"""
    Generate a course outline with exactly {chapter_count} chapters and {subchapter_count} subchapters per chapter for the topic '{prompt}'.
    The structure must strictly follow this JSON format:
    {{
        "Chapter 1: Chapter Title": ["Subchapter Title 1", "Subchapter Title 2", ..., "Subchapter Title {subchapter_count}"],
        "Chapter 2: Chapter Title": ["Subchapter Title 1", "Subchapter Title 2", ..., "Subchapter Title {subchapter_count}"],
        ...
    }}
    Ensure there are exactly {chapter_count} chapters and exactly {subchapter_count} subchapters per chapter.
    """

    request_payload = [
        {"role": "system", "content": "You are an expert course designer."},
        {"role": "user", "content": instruction},
    ]
    
    try:
        openai_response = call_openai_outline_api(request_payload, chapter_count, subchapter_count)
        return jsonify(openai_response), 200
    except Exception as openai_error:
        print(f"OpenAI request failed: {openai_error}")
        
        try:
            anthropic_response = call_anthropic_outline_api(prompt, chapter_count, subchapter_count)
            return jsonify(anthropic_response), 200
        except Exception as anthropic_error:
            print(f"Anthropic request failed: {anthropic_error}")
            return jsonify({"error": "Both OpenAI and Anthropic requests failed."}), 500

@app.route("/api/v1/course/generate-content", methods=["POST"])
def generate_content():
    data = request.get_json()
    prompt = data.get('prompt')
    outline = data['outline']
    include_images = data.get('image', False)

    def generate_content_with_images(prompt, chapter_name, subchapter_name, include_images):
        gpt_response, image_descriptions = fetch_content(prompt, chapter_name, subchapter_name, include_images)
        image_urls = fetch_images_for_content(gpt_response) if include_images else []

        content_with_images = insert_images_into_content(gpt_response, image_descriptions, image_urls)
        
        return {
            "content": content_with_images,
            "image_urls": image_urls
        }

    def notify_user(content, chapter_name, subchapter_name):
        socketio.emit('subchapter_created', {
          'chapterName': chapter_name,
          'subchapterName': subchapter_name,
          'content': content
        })
        print("Subchapter Created: ", chapter_name, subchapter_name)

    def process_chapters():
        with ThreadPoolExecutor() as executor:
            first_subchapter_flag = False

            for chapter_name, subchapters in outline.items():
                for subchapter_index, subchapter_name in enumerate(subchapters):
                    future_fetch = executor.submit(generate_content_with_images, prompt, chapter_name, subchapter_name, include_images)
                    result = future_fetch.result()

                    if result:
                        if not first_subchapter_flag and subchapter_index == 0:
                            first_subchapter_flag = True
                            socketio.emit('first_subchapter_created', {
                                'chapterName': chapter_name,
                                'subchapterName': subchapter_name,
                                'content': result
                            })
                            print("First Subchapter Created: ", chapter_name, subchapter_name)
                        else:
                            notify_user(result, chapter_name, subchapter_name)

            socketio.emit('content_generation_complete', {'message': 'All content has been generated.'})
            print("Finished")

    socketio.start_background_task(process_chapters)
    return jsonify({"message": "Content generation started."})

@app.route("/api/v1/course/save-course", methods=["POST"])
def save_course():
    try:
        data = request.get_json()
        course_data = data.get('course')
        prompt = data.get('prompt')

        if not course_data:
            return jsonify({"error": "Missing 'course' data in the request body"}), 400

        date = datetime.now(UTC)

        new_course = Course(prompt=prompt, course=course_data, date=date)

        db.session.add(new_course)
        db.session.commit()

        return jsonify({"message": "Course saved successfully!", "course_id": new_course.id}), 201

    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500

@app.route("/api/v1/course/get-courses", methods=["GET"])
def get_courses():
    try:
        courses = Course.query.all()

        courses_list = [
            {
                "id": course.id,
                "prompt": course.prompt,
                "course": course.course,
                "date": course.date.isoformat()
            }
            for course in courses
        ]

        return jsonify({ "status": "success", "courses": courses_list }), 200

    except Exception as e:
        return jsonify({ "status": "error", "message": str(e) }), 500
    
@app.route("/api/v1/course/get-course/<int:id>", methods=["GET"])
def get_course_by_id(id):
    try:
        course = Course.query.get_or_404(id)

        course_data = {
            "id": course.id,
            "prompt": course.prompt,
            "course": course.course,
            "date": course.date.isoformat()
        }

        return jsonify({ "status": "success", "course": course_data }), 200

    except Exception as e:
        return jsonify({ "status": "error", "message": str(e) }), 500