"""焦炭只读业务预览；独立于legacy r1规则，不写正式记录。"""
from uebench.domain.gb21342 import CokeAssessmentInput, CokeAssessmentResult, assess_coke


def preview_coke(request: CokeAssessmentInput) -> CokeAssessmentResult:
    return assess_coke(request)
