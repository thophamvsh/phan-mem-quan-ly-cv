from rest_framework import serializers

class AiChatRequestSerializer(serializers.Serializer):
    content = serializers.CharField(allow_blank=False, trim_whitespace=True)
    session_id = serializers.CharField(required=False, allow_blank=True)
    stream = serializers.BooleanField(required=False, default=False)
    provider = serializers.ChoiceField(
        choices=("openai", "deepseek"),
        required=False,
        allow_blank=True,
    )
    model = serializers.CharField(required=False, allow_blank=True, default="")
