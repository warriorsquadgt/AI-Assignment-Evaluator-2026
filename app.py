import streamlit as st
import ollama
import json
import re
from pypdf import PdfReader
from docx import Document


# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="AI Assignment Evaluator",
    page_icon="📝",
    layout="wide"
)

st.title("📝 AI Student Assignment Evaluator")
st.write("Upload a student's assignment and let Ollama evaluate it.")


# =========================================================
# PDF TEXT EXTRACTION
# =========================================================

def extract_pdf_text(file):

    reader = PdfReader(file)

    text = ""

    for page in reader.pages:

        page_text = page.extract_text()

        if page_text:
            text += page_text + "\n"

    return text


# =========================================================
# DOCX TEXT EXTRACTION
# =========================================================

def extract_docx_text(file):

    document = Document(file)

    text = []

    for paragraph in document.paragraphs:

        text.append(paragraph.text)

    return "\n".join(text)


# =========================================================
# CLEAN AI JSON RESPONSE
# =========================================================

def parse_ai_response(content):

    if not content:

        return None

    content = content.strip()

    # -----------------------------------------------------
    # Remove markdown code fences
    # -----------------------------------------------------

    content = re.sub(
        r"```json\s*",
        "",
        content,
        flags=re.IGNORECASE
    )

    content = re.sub(
        r"```\s*",
        "",
        content
    )

    content = content.strip()

    # -----------------------------------------------------
    # Try normal JSON
    # -----------------------------------------------------

    try:

        return json.loads(content)

    except json.JSONDecodeError:

        pass

    # -----------------------------------------------------
    # Try to find JSON object inside response
    # -----------------------------------------------------

    start = content.find("{")
    end = content.rfind("}")

    if start != -1 and end != -1 and end > start:

        json_text = content[start:end + 1]

        try:

            return json.loads(json_text)

        except json.JSONDecodeError:

            pass

    return None


# =========================================================
# VALIDATE RESULT
# =========================================================

def validate_result(result, max_marks):

    if not isinstance(result, dict):

        return None

    # Required fields

    required_fields = [
        "marks",
        "percentage",
        "grade",
        "overall_remark",
        "strengths",
        "weaknesses",
        "improvements"
    ]

    for field in required_fields:

        if field not in result:

            return None

    # -----------------------------------------------------
    # Marks
    # -----------------------------------------------------

    try:

        marks = float(result["marks"])

    except:

        return None

    # Keep marks inside allowed range

    marks = max(
        0,
        min(marks, max_marks)
    )

    # -----------------------------------------------------
    # Calculate percentage ourselves
    # -----------------------------------------------------

    percentage = (marks / max_marks) * 100

    # -----------------------------------------------------
    # Convert marks to integer when appropriate
    # -----------------------------------------------------

    if marks.is_integer():

        marks = int(marks)

    result["marks"] = marks

    result["percentage"] = round(
        percentage,
        2
    )

    # -----------------------------------------------------
    # Make sure lists exist
    # -----------------------------------------------------

    if not isinstance(
        result["strengths"],
        list
    ):

        result["strengths"] = [
            str(result["strengths"])
        ]

    if not isinstance(
        result["weaknesses"],
        list
    ):

        result["weaknesses"] = [
            str(result["weaknesses"])
        ]

    if not isinstance(
        result["improvements"],
        list
    ):

        result["improvements"] = [
            str(result["improvements"])
        ]

    return result


# =========================================================
# TEXT ASSIGNMENT EVALUATION
# =========================================================

def evaluate_text_assignment(
    question,
    rubric,
    student_answer,
    max_marks,
    model
):

    prompt = f"""
You are an experienced academic evaluator.

Evaluate the student's assignment fairly and objectively.

ASSIGNMENT QUESTION:
{question}

EVALUATION RUBRIC:
{rubric}

MAXIMUM MARKS:
{max_marks}

STUDENT ANSWER:
{student_answer}

Evaluate the answer based ONLY on:

- Correctness
- Relevance
- Completeness
- Understanding
- Quality of explanation
- Quality of reasoning
- The provided rubric

Do not give marks simply because the answer is long.

Return ONLY a JSON object.

The JSON must have exactly these fields:

{{
    "marks": 0,
    "percentage": 0,
    "grade": "A",
    "overall_remark": "Brief explanation of the student's performance.",
    "strengths": [
        "Strength 1",
        "Strength 2"
    ],
    "weaknesses": [
        "Weakness 1",
        "Weakness 2"
    ],
    "improvements": [
        "Improvement 1",
        "Improvement 2"
    ]
}}

Rules:

1. Marks must be between 0 and {max_marks}.
2. Evaluate the student's actual answer.
3. Do not reward length alone.
4. Do not invent information.
5. Give a realistic grade.
6. Give specific strengths.
7. Give specific weaknesses.
8. Give practical improvements.
"""

    try:

        response = ollama.chat(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        content = response["message"]["content"]

        result = parse_ai_response(content)

        if result is None:

            st.error(
                "Ollama returned an invalid evaluation."
            )

            st.write("Raw Ollama response:")

            st.code(
                content,
                language="text"
            )

            return None

        return validate_result(
            result,
            max_marks
        )

    except Exception as e:

        st.error(
            f"Error communicating with Ollama: {e}"
        )

        return None


# =========================================================
# IMAGE ASSIGNMENT EVALUATION
# =========================================================

def evaluate_image_assignment(
    question,
    rubric,
    image_bytes,
    max_marks
):

    prompt = f"""
You are an experienced academic evaluator.

The student's assignment is provided as an image.

Carefully read the student's answer from the image.

ASSIGNMENT QUESTION:
{question}

EVALUATION RUBRIC:
{rubric}

MAXIMUM MARKS:
{max_marks}

Evaluate the student's answer based ONLY on:

- Correctness
- Relevance
- Completeness
- Understanding
- Quality of explanation
- Quality of reasoning
- The provided rubric

IMPORTANT:

1. Carefully read ALL visible student writing.
2. Evaluate only what the student actually wrote.
3. Do not invent missing words or information.
4. If handwriting is unclear, do not assume what it says.
5. Do not give marks simply because the answer is long.
6. Follow the provided marking rubric.
7. Be fair and consistent.

Return ONLY a JSON object.

The JSON must have exactly these fields:

{{
    "marks": 0,
    "percentage": 0,
    "grade": "A",
    "overall_remark": "Brief explanation of the student's performance.",
    "strengths": [
        "Strength 1",
        "Strength 2"
    ],
    "weaknesses": [
        "Weakness 1",
        "Weakness 2"
    ],
    "improvements": [
        "Improvement 1",
        "Improvement 2"
    ]
}}

Rules:

1. Marks must be between 0 and {max_marks}.
2. Evaluate the actual answer visible in the image.
3. Do not reward length alone.
4. Do not invent information.
5. Give a realistic grade.
6. Give specific strengths.
7. Give specific weaknesses.
8. Give practical improvements.
"""

    try:

        # -------------------------------------------------
        # Send image directly to Ollama
        # -------------------------------------------------

        response = ollama.chat(
            model="gemma4:31b-cloud",
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                    "images": [image_bytes]
                }
            ]
        )

        # -------------------------------------------------
        # Get AI response
        # -------------------------------------------------

        content = response["message"]["content"]

        # -------------------------------------------------
        # Check empty response
        # -------------------------------------------------

        if not content or not content.strip():

            st.error(
                "Ollama returned an empty response."
            )

            return None

        # -------------------------------------------------
        # Parse JSON
        # -------------------------------------------------

        result = parse_ai_response(
            content
        )

        # -------------------------------------------------
        # Invalid JSON
        # -------------------------------------------------

        if result is None:

            st.error(
                "Ollama did not return valid evaluation data."
            )

            st.write(
                "Raw Ollama response:"
            )

            st.code(
                content,
                language="text"
            )

            return None

        # -------------------------------------------------
        # Validate result
        # -------------------------------------------------

        result = validate_result(
            result,
            max_marks
        )

        if result is None:

            st.error(
                "The AI response is missing required evaluation fields."
            )

            st.write(
                "Raw Ollama response:"
            )

            st.code(
                content,
                language="text"
            )

            return None

        return result

    except Exception as e:

        st.error(
            f"Error communicating with Ollama Vision: {e}"
        )

        return None


# =========================================================
# SIDEBAR
# =========================================================

st.sidebar.header(
    "⚙️ Evaluation Settings"
)


max_marks = st.sidebar.number_input(
    "Maximum Marks",
    min_value=1,
    max_value=1000,
    value=100
)


text_model = st.sidebar.selectbox(
    "Text Ollama Model",
    [
        "gemma4:31b-cloud"
    ]
)


# =========================================================
# ASSIGNMENT DETAILS
# =========================================================

st.header(
    "1️⃣ Assignment Details"
)


question = st.text_area(
    "Assignment Question",
    height=150,
    placeholder=(
        "Example: Explain the causes and effects of inflation."
    )
)


rubric = st.text_area(
    "Evaluation Rubric",
    height=180,
    placeholder="""Example:
- Understanding of the concept: 30 marks
- Accuracy: 25 marks
- Explanation: 20 marks
- Examples: 15 marks
- Presentation: 10 marks"""
)


# =========================================================
# STUDENT INFORMATION
# =========================================================

st.header(
    "2️⃣ Student Information"
)


student_name = st.text_input(
    "Student Name",
    placeholder="Enter student name"
)


# =========================================================
# ASSIGNMENT UPLOAD
# =========================================================

st.header(
    "3️⃣ Upload Student Assignment"
)


uploaded_file = st.file_uploader(
    "Upload the student's assignment",
    type=[
        "jpg",
        "jpeg",
        "png",
        "webp",
        "pdf",
        "docx",
        "txt"
    ],
    help=(
        "Upload a photo/scan of the assignment "
        "or a PDF/DOCX/TXT file."
    )
)


student_answer = ""
image_bytes = None
file_type = None


# =========================================================
# PROCESS UPLOADED FILE
# =========================================================

if uploaded_file:

    file_type = (
        uploaded_file.name
        .split(".")[-1]
        .lower()
    )

    st.success(
        f"Assignment uploaded: {uploaded_file.name}"
    )

    # -----------------------------------------------------
    # IMAGE
    # -----------------------------------------------------

    if file_type in [
        "jpg",
        "jpeg",
        "png",
        "webp"
    ]:

        image_bytes = uploaded_file.getvalue()

        st.subheader(
            "🖼️ Assignment Preview"
        )

        st.image(
            image_bytes,
            caption="Uploaded Student Assignment",
            use_container_width=True
        )

    # -----------------------------------------------------
    # PDF
    # -----------------------------------------------------

    elif file_type == "pdf":

        try:

            student_answer = extract_pdf_text(
                uploaded_file
            )

            with st.expander(
                "📄 Preview Extracted Text"
            ):

                st.text(
                    student_answer[:10000]
                )

        except Exception as e:

            st.error(
                f"Could not read PDF: {e}"
            )

    # -----------------------------------------------------
    # DOCX
    # -----------------------------------------------------

    elif file_type == "docx":

        try:

            student_answer = extract_docx_text(
                uploaded_file
            )

            with st.expander(
                "📄 Preview Extracted Text"
            ):

                st.text(
                    student_answer[:10000]
                )

        except Exception as e:

            st.error(
                f"Could not read DOCX: {e}"
            )

    # -----------------------------------------------------
    # TXT
    # -----------------------------------------------------

    elif file_type == "txt":

        try:

            student_answer = (
                uploaded_file
                .read()
                .decode(
                    "utf-8",
                    errors="ignore"
                )
            )

            with st.expander(
                "📄 Preview Student Answer"
            ):

                st.text(
                    student_answer[:10000]
                )

        except Exception as e:

            st.error(
                f"Could not read TXT: {e}"
            )


# =========================================================
# EVALUATE BUTTON
# =========================================================

st.divider()


if st.button(
    "🚀 Evaluate Assignment",
    type="primary",
    use_container_width=True
):

    # -----------------------------------------------------
    # Check question
    # -----------------------------------------------------

    if not question.strip():

        st.warning(
            "Please enter the assignment question."
        )

        st.stop()

    # -----------------------------------------------------
    # Check rubric
    # -----------------------------------------------------

    if not rubric.strip():

        st.warning(
            "Please enter an evaluation rubric."
        )

        st.stop()

    # -----------------------------------------------------
    # Check file
    # -----------------------------------------------------

    if not uploaded_file:

        st.warning(
            "Please upload the student's assignment."
        )

        st.stop()

    # -----------------------------------------------------
    # IMAGE EVALUATION
    # -----------------------------------------------------

    if image_bytes:

        with st.spinner(
            "🤖 Ollama Vision is reading and evaluating the assignment..."
        ):

            result = evaluate_image_assignment(
                question,
                rubric,
                image_bytes,
                max_marks
            )

        if result is None:

            st.stop()

    # -----------------------------------------------------
    # TEXT / PDF / DOCX EVALUATION
    # -----------------------------------------------------

    else:

        if not student_answer.strip():

            st.warning(
                "The uploaded file does not contain readable text."
            )

            st.stop()

        with st.spinner(
            "🤖 Ollama is evaluating the assignment..."
        ):

            result = evaluate_text_assignment(
                question,
                rubric,
                student_answer,
                max_marks,
                text_model
            )

        if result is None:

            st.stop()

    # =====================================================
    # DISPLAY RESULT
    # =====================================================

    st.success(
        "✅ Evaluation completed!"
    )

    st.header(
        "📊 Evaluation Result"
    )

    # -----------------------------------------------------
    # Student Name
    # -----------------------------------------------------

    if student_name.strip():

        st.subheader(
            f"Student: {student_name}"
        )

    # -----------------------------------------------------
    # Score
    # -----------------------------------------------------

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "Marks",
            f"{result['marks']} / {max_marks}"
        )

    with col2:

        st.metric(
            "Percentage",
            f"{result['percentage']}%"
        )

    with col3:

        st.metric(
            "Grade",
            result["grade"]
        )

    # -----------------------------------------------------
    # Overall Remark
    # -----------------------------------------------------

    st.subheader(
        "💬 Overall Remark"
    )

    st.info(
        result["overall_remark"]
    )

    # -----------------------------------------------------
    # Strengths
    # -----------------------------------------------------

    st.subheader(
        "✅ Strengths"
    )

    for strength in result["strengths"]:

        st.write(
            f"• {strength}"
        )

    # -----------------------------------------------------
    # Weaknesses
    # -----------------------------------------------------

    st.subheader(
        "⚠️ Areas for Improvement"
    )

    for weakness in result["weaknesses"]:

        st.write(
            f"• {weakness}"
        )

    # -----------------------------------------------------
    # Improvements
    # -----------------------------------------------------

    st.subheader(
        "💡 Suggestions for Improvement"
    )

    for improvement in result["improvements"]:

        st.write(
            f"• {improvement}"
        )

    # -----------------------------------------------------
    # Raw JSON
    # -----------------------------------------------------

    with st.expander(
        "🔍 View AI Evaluation Data"
    ):

        st.json(result)