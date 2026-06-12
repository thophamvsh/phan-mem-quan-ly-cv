from rest_framework import serializers


class AiChatRequestSerializer(serializers.Serializer):
    content = serializers.CharField(allow_blank=False, trim_whitespace=True)
    session_id = serializers.CharField(required=False, allow_blank=True)
    stream = serializers.BooleanField(required=False, default=False)


class AiChatResponseSerializer(serializers.Serializer):
    session_id = serializers.CharField()
    response = serializers.CharField()
    model = serializers.CharField()
    total_tokens = serializers.IntegerField()
    cost_usd = serializers.FloatField()
    latency_ms = serializers.IntegerField()
    tools_called = serializers.IntegerField()
