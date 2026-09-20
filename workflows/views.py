import uuid

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import JWTAuthentication
from workflows.mongo import get_workflow_templates_collection
from workflows.serializers import WORKFLOW_TYPES, WorkflowStepSerializer

DEFAULT_STEPS = {
    "Recruitment": [
        {"step_name": "Resume Screening", "who": "Recruiter", "tat_days": 2},
        {"step_name": "Technical Interview", "who": "Hiring Manager", "tat_days": 3},
        {"step_name": "HR Interview", "who": "HR", "tat_days": 2},
        {"step_name": "Offer Approval", "who": "HR Head", "tat_days": 1},
    ],
    "Onboarding": [
        {"step_name": "Document Collection", "who": "HR", "tat_days": 1},
        {"step_name": "IT Setup", "who": "IT", "tat_days": 1},
        {"step_name": "Policy Acceptance", "who": "Employee", "tat_days": 1},
        {"step_name": "Induction", "who": "HR", "tat_days": 1},
    ],
    "Exit": [
        {"step_name": "Resignation Acceptance", "who": "Manager", "tat_days": 1},
        {"step_name": "Knowledge Transfer", "who": "Employee", "tat_days": 7},
        {"step_name": "Asset Return", "who": "Admin/IT", "tat_days": 2},
        {"step_name": "Full & Final Settlement", "who": "Finance", "tat_days": 5},
    ],
}


def build_default_steps(workflow_type):
    steps = []
    for index, step in enumerate(DEFAULT_STEPS[workflow_type]):
        steps.append(
            {
                "id": uuid.uuid4().hex,
                "step_name": step["step_name"],
                "who": step["who"],
                "tat_days": step["tat_days"],
                "sort_order": index,
            }
        )
    return steps


def get_or_create_template(workflow_type):
    collection = get_workflow_templates_collection()
    template = collection.find_one({"type": workflow_type})
    if template:
        return template

    template = {"type": workflow_type, "steps": build_default_steps(workflow_type)}
    collection.insert_one(template)
    return template


def serialize_steps(template):
    steps = sorted(template.get("steps", []), key=lambda s: s.get("sort_order", 0))
    return steps


def snapshot_steps_for_instance(workflow_type):
    """Build a fresh, independent copy of a workflow template's steps to attach
    to a specific candidate/employee/separation record. Each snapshot gets its
    own step ids (separate from the template's) plus done/done_date fields, so
    later edits to the admin template never retroactively change records that
    already copied it — matching this app's existing snapshot pattern (see
    employees' family/facilities arrays, recruitment's candidate creation)."""
    template = get_or_create_template(workflow_type)
    steps = serialize_steps(template)
    return [
        {
            "id": uuid.uuid4().hex,
            "step_name": step.get("step_name", ""),
            "who": step.get("who", ""),
            "tat_days": step.get("tat_days", 1),
            "done": False,
            "done_date": None,
        }
        for step in steps
    ]


class WorkflowStepListCreateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, workflow_type):
        if workflow_type not in WORKFLOW_TYPES:
            return Response(
                {"detail": "Unknown workflow type."}, status=status.HTTP_404_NOT_FOUND
            )

        template = get_or_create_template(workflow_type)
        return Response(serialize_steps(template))

    def post(self, request, workflow_type):
        if workflow_type not in WORKFLOW_TYPES:
            return Response(
                {"detail": "Unknown workflow type."}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = WorkflowStepSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        template = get_or_create_template(workflow_type)
        existing_steps = template.get("steps", [])
        max_sort_order = max([s.get("sort_order", 0) for s in existing_steps], default=-1)

        new_step = {
            "id": uuid.uuid4().hex,
            "step_name": data["step_name"],
            "who": data.get("who", ""),
            "tat_days": data.get("tat_days", 1),
            "sort_order": max_sort_order + 1,
        }

        get_workflow_templates_collection().update_one(
            {"type": workflow_type}, {"$push": {"steps": new_step}}
        )

        updated = get_workflow_templates_collection().find_one({"type": workflow_type})
        return Response(serialize_steps(updated), status=status.HTTP_201_CREATED)


class WorkflowStepDetailView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, workflow_type, step_id):
        if workflow_type not in WORKFLOW_TYPES:
            return Response(
                {"detail": "Unknown workflow type."}, status=status.HTTP_404_NOT_FOUND
            )

        template = get_or_create_template(workflow_type)
        steps = sorted(template.get("steps", []), key=lambda s: s.get("sort_order", 0))
        step_index = next((i for i, s in enumerate(steps) if s.get("id") == step_id), None)
        if step_index is None:
            return Response(
                {"detail": "Step not found."}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = WorkflowStepSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        move = data.pop("move", None)
        if move:
            swap_index = step_index - 1 if move == "up" else step_index + 1
            if 0 <= swap_index < len(steps):
                steps[step_index]["sort_order"], steps[swap_index]["sort_order"] = (
                    steps[swap_index]["sort_order"],
                    steps[step_index]["sort_order"],
                )

        if data:
            steps[step_index].update(data)

        get_workflow_templates_collection().update_one(
            {"type": workflow_type}, {"$set": {"steps": steps}}
        )

        updated = get_workflow_templates_collection().find_one({"type": workflow_type})
        return Response(serialize_steps(updated))

    def delete(self, request, workflow_type, step_id):
        if workflow_type not in WORKFLOW_TYPES:
            return Response(
                {"detail": "Unknown workflow type."}, status=status.HTTP_404_NOT_FOUND
            )

        template = get_or_create_template(workflow_type)
        steps = template.get("steps", [])
        if not any(s.get("id") == step_id for s in steps):
            return Response(
                {"detail": "Step not found."}, status=status.HTTP_404_NOT_FOUND
            )

        get_workflow_templates_collection().update_one(
            {"type": workflow_type}, {"$pull": {"steps": {"id": step_id}}}
        )

        updated = get_workflow_templates_collection().find_one({"type": workflow_type})
        return Response(serialize_steps(updated))
