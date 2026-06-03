import json

from documents.models import Document
from documents.services.retrieval import search_documents


DOCUMENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_internal_documents",
            "description": "Tra cuu tai lieu noi bo da upload vao kho RAG, phu hop cho quy trinh, quy dinh, huong dan, bao cao va noi dung van ban.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Cau hoi hoac tu khoa can tim trong tai lieu noi bo.",
                    },
                    "factory": {
                        "type": "string",
                        "enum": [
                            Document.FACTORY_GENERAL,
                            Document.FACTORY_SONGHINH,
                            Document.FACTORY_VINHSON,
                            Document.FACTORY_THUONGKONTUM,
                        ],
                        "description": "Nha may can gioi han pham vi tim kiem, neu nguoi dung neu ro.",
                    },
                    "document_type": {
                        "type": "string",
                        "description": "Loai tai lieu neu biet, vi du quy_trinh, quy_dinh, bao_cao.",
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 8,
                        "default": 3,
                    },
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    }
]


def handle_document_tool_call(user, tool_call):
    args = json.loads(getattr(tool_call.function, "arguments", "") or "{}")
    results = search_documents(
        user,
        query=args.get("query", ""),
        factory=args.get("factory", ""),
        document_type=args.get("document_type", ""),
        limit=args.get("limit", 3),
    )
    if not results:
        return {"content": "Khong tim thay noi dung phu hop trong kho tai lieu noi bo."}

    lines = ["Ket qua tra cuu tai lieu noi bo:"]
    for index, item in enumerate(results, start=1):
        heading = f" > {item['heading_path']}" if item.get("heading_path") else ""
        page_str = f"Trang: {item['page_num']}" if item.get('page_num') else ""
        link_str = f"Link tai: {item['file_url']}" if item.get('file_url') else ""
        meta_parts = [p for p in [page_str, link_str] if p]
        meta_info = f" ({', '.join(meta_parts)})" if meta_parts else ""

        lines.append(
            f"[{index}] Nguon: {item['document_title']}{heading}{meta_info} (Score: {item['score']})\n"
            f"Noi dung: {item['content']}"
        )
    return {"content": "\n\n".join(lines)}
