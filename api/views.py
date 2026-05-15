from django.db.models import Count
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework import status

from api.models import DataSource, EnterpriseUser, QueryAudit
from api.serializers import DataSourceSerializer, EnterpriseUserSerializer, QueryAuditSerializer
from api.services.generation import generator
from api.services.ingestion import ocr_status, save_uploaded_source
from api.services.retrieval import answer_question


@api_view(["GET"])
def home(request):
    return Response(
        {
            "name": "Enterprise RAG Intelligence API",
            "status": "running",
            "frontend": "Open the React app at http://127.0.0.1:5173 or the active Vite port.",
            "endpoints": {
                "health": "/api/health/",
                "users": "/api/users/",
                "sources": "/api/sources/",
                "query": "/api/query/",
                "upload": "/api/upload/",
                "audits": "/api/audits/",
            },
        }
    )


@api_view(["GET"])
def health(request):
    return Response({"status": "ok", "model": generator.status, "ocr": ocr_status()})


@api_view(["GET"])
def users(request):
    serializer = EnterpriseUserSerializer(EnterpriseUser.objects.all().order_by("department", "display_name"), many=True)
    return Response(serializer.data)


@api_view(["GET"])
def sources(request):
    queryset = DataSource.objects.annotate(chunk_count=Count("chunks")).order_by("source_type", "title")
    return Response(DataSourceSerializer(queryset, many=True).data)


@api_view(["POST"])
def query(request):
    username = request.data.get("username")
    question = (request.data.get("question") or "").strip()
    if not username or not question:
        return Response({"detail": "username and question are required."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        user = EnterpriseUser.objects.get(username=username)
    except EnterpriseUser.DoesNotExist:
        return Response({"detail": "Unknown enterprise user."}, status=status.HTTP_404_NOT_FOUND)
    return Response(answer_question(user, question))


def parse_csv_value(value):
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


@api_view(["POST"])
@parser_classes([MultiPartParser, FormParser])
def upload_source(request):
    uploaded_file = request.FILES.get("file")
    if not uploaded_file:
        return Response({"detail": "file is required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        clearance = int(request.data.get("min_clearance") or 1)
    except ValueError:
        return Response({"detail": "min_clearance must be a number."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        source, ingest_result = save_uploaded_source(
            uploaded_file=uploaded_file,
            title=(request.data.get("title") or "").strip(),
            departments=parse_csv_value(request.data.get("departments")),
            roles=parse_csv_value(request.data.get("allowed_roles")),
            clearance=clearance,
            sensitivity=(request.data.get("sensitivity") or "internal").strip(),
            description=(request.data.get("description") or "").strip(),
        )
    except Exception as exc:
        return Response(
            {
                "detail": "Could not parse uploaded source.",
                "error": str(exc),
                "ocr": ocr_status(),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    payload = DataSourceSerializer(
        DataSource.objects.annotate(chunk_count=Count("chunks")).get(id=source.id)
    ).data
    return Response(
        {
            "source": payload,
            "chunks_created": ingest_result["chunks"],
            "parser_details": ingest_result["parser_details"],
            "ocr": ocr_status(),
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
def audits(request):
    queryset = QueryAudit.objects.select_related("user").order_by("-created_at")[:20]
    return Response(QueryAuditSerializer(queryset, many=True).data)
