from rest_framework import serializers

from rocky.views.mixins import EnrichedReport


class ReportSerializer(serializers.BaseSerializer):
    def to_representation(self, instance):
        if isinstance(instance, EnrichedReport):
            report = instance.report
        else:
            report = instance
        return {
            "id": report.reference,
            "valid_time": report.observed_at,
            "name": report.name,
            "report_type": report.report_type,
            "generated_at": report.date_generated,
            "intput_oois": report.input_oois,
        }


class ReportRecipeSerializer(serializers.Serializer):
    id = serializers.UUIDField(source="recipe_id", required=False)
    report_name_format = serializers.CharField()

    input_recipe = serializers.DictField()
    report_type = serializers.CharField()
    asset_report_types = serializers.ListField(child=serializers.CharField())

    cron_expression = serializers.CharField()
    start_date = serializers.DateField(write_only=True, required=False)
