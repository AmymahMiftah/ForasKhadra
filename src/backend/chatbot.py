import os
from groq import Groq
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

SYSTEM_PROMPT = """أنت مساعد ذكي لمنصة "فرص خضراء"، منصة عربية تساعد الشباب العربي في إيجاد المنح الدراسية والتدريب والوظائف والمدارس الصيفية.

مهامك:
- أجب على أي سؤال يتعلق بالمنح والفرص الدراسية والتدريب والوظائف
- قدم معلومات دقيقة ومفيدة عن الفرص المتاحة حول العالم
- ساعد المستخدمين في فهم متطلبات التقديم والمواعيد النهائية
- قدم نصائح للشباب العربي حول كيفية الحصول على الفرص
- أجب باللغة التي يستخدمها المستخدم (عربي، إنجليزي، أو مزيج)
- كن ودوداً ومشجعاً ومفيداً
- إذا سألك عن فرصة معينة، أعطِ كل التفاصيل التي تعرفها عنها
"""

def chat(history: list, opportunities: list = None, active_embeddings=None, tag_index: dict = None) -> dict:
    #history
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        temperature=0.5,
        max_tokens=800
    )

    return {
        "answer": response.choices[0].message.content,
        "sources": []
    }