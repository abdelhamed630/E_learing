"""
Serializers للامتحانات — نسخة مُصلحة بالكامل
"""
from rest_framework import serializers
from .models import Exam, Question, Answer, ExamAttempt, StudentAnswer


# ───────────────────────────────────────────────────
#  مساعد مشترك
# ───────────────────────────────────────────────────
def _get_student(request):
    if not request:
        return None
    from students.models import Student
    student, _ = Student.objects.get_or_create(user=request.user)
    return student


# ───────────────────────────────────────────────────
#  Serializers الأساسية
# ───────────────────────────────────────────────────
class AnswerSerializer(serializers.ModelSerializer):
    """للطالب — بدون is_correct"""
    class Meta:
        model  = Answer
        fields = ['id', 'answer_text', 'order']


class QuestionSerializer(serializers.ModelSerializer):
    answers   = AnswerSerializer(many=True, read_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model  = Question
        fields = ['id', 'question_text', 'question_type', 'image', 'image_url', 'points', 'order', 'answers']

    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image and hasattr(obj.image, 'url'):
            try:
                return request.build_absolute_uri(obj.image.url) if request else obj.image.url
            except Exception:
                pass
        return None


# ───────────────────────────────────────────────────
#  ExamSerializer (قائمة الامتحانات للطالب)
# ───────────────────────────────────────────────────
class ExamSerializer(serializers.ModelSerializer):
    total_questions = serializers.SerializerMethodField()
    total_points    = serializers.SerializerMethodField()
    course_title    = serializers.CharField(source='course.title', read_only=True)
    attempts_used   = serializers.SerializerMethodField()
    attempts_left   = serializers.SerializerMethodField()
    best_score      = serializers.SerializerMethodField()

    class Meta:
        model  = Exam
        fields = [
            'id', 'title', 'description', 'duration', 'passing_score',
            'max_attempts', 'shuffle_questions', 'show_result_immediately',
            'allow_review', 'show_correct_answers',
            'total_questions', 'total_points',
            'course_title', 'attempts_used', 'attempts_left', 'best_score',
        ]

    def get_total_questions(self, obj): return obj.total_questions
    def get_total_points(self, obj):    return obj.total_points

    def get_attempts_used(self, obj):
        student = _get_student(self.context.get('request'))
        if not student: return 0
        return ExamAttempt.objects.filter(
            student=student, exam=obj
        ).exclude(status='in_progress').count()

    def get_attempts_left(self, obj):
        return max(0, obj.max_attempts - self.get_attempts_used(obj))

    def get_best_score(self, obj):
        student = _get_student(self.context.get('request'))
        if not student: return None
        best = ExamAttempt.objects.filter(
            student=student, exam=obj, status='graded'
        ).order_by('-score').first()
        return float(best.score) if best else None


class ExamDetailSerializer(ExamSerializer):
    """مع الأسئلة"""
    questions = serializers.SerializerMethodField()

    def get_questions(self, obj):
        return QuestionSerializer(obj.questions.all(), many=True, context=self.context).data

    class Meta(ExamSerializer.Meta):
        fields = ExamSerializer.Meta.fields + ['instructions', 'questions']


# ───────────────────────────────────────────────────
#  Submit Serializers
# ───────────────────────────────────────────────────
class StartExamSerializer(serializers.Serializer):
    exam_id = serializers.IntegerField(required=True)


class SubmitExamSerializer(serializers.Serializer):
    answers = serializers.ListField(child=serializers.DictField(), min_length=1)

    def validate_answers(self, value):
        for item in value:
            if 'question_id' not in item:
                raise serializers.ValidationError("كل إجابة يجب أن تحتوي على question_id")
            if 'answer_ids' not in item or not isinstance(item['answer_ids'], list) or not item['answer_ids']:
                raise serializers.ValidationError("كل إجابة يجب أن تحتوي على answer_ids قائمة غير فارغة")
        return value


# ───────────────────────────────────────────────────
#  StudentAnswer Serializer
# ───────────────────────────────────────────────────
class StudentAnswerSerializer(serializers.ModelSerializer):
    question_text   = serializers.CharField(source='question.question_text', read_only=True)
    question_type   = serializers.CharField(source='question.question_type', read_only=True)
    question_points = serializers.IntegerField(source='question.points', read_only=True)
    question_image  = serializers.SerializerMethodField()
    selected_answers = AnswerSerializer(many=True, read_only=True)
    correct_answers  = serializers.SerializerMethodField()
    explanation      = serializers.CharField(source='question.explanation', read_only=True)

    class Meta:
        model  = StudentAnswer
        fields = [
            'id', 'question', 'question_text', 'question_type',
            'question_points', 'question_image', 'selected_answers', 'correct_answers',
            'is_correct', 'points_earned', 'explanation', 'answered_at',
        ]

    def get_question_image(self, obj):
        request = self.context.get('request')
        if obj.question.image and hasattr(obj.question.image, 'url'):
            try:
                return request.build_absolute_uri(obj.question.image.url) if request else obj.question.image.url
            except Exception:
                pass
        return None

    def get_correct_answers(self, obj):
        """يظهر الإجابات الصحيحة فقط لو الامتحان انتهى و show_correct_answers=True"""
        attempt = obj.attempt
        if attempt.status == 'graded' and attempt.exam.show_correct_answers:
            return AnswerSerializer(obj.question.answers.filter(is_correct=True), many=True).data
        return None


# ───────────────────────────────────────────────────
#  ExamAttempt Serializer
# ───────────────────────────────────────────────────
class ExamAttemptSerializer(serializers.ModelSerializer):
    exam_title   = serializers.CharField(source='exam.title', read_only=True)
    course_title = serializers.CharField(source='exam.course.title', read_only=True)
    # @property fields → SerializerMethodField
    time_remaining = serializers.SerializerMethodField()
    duration_taken = serializers.SerializerMethodField()
    is_expired     = serializers.SerializerMethodField()

    def get_time_remaining(self, obj): return obj.time_remaining
    def get_duration_taken(self, obj): return obj.duration_taken
    def get_is_expired(self, obj):     return obj.is_expired

    class Meta:
        model  = ExamAttempt
        fields = [
            'id', 'exam', 'exam_title', 'course_title',
            'status', 'score', 'points_earned', 'passed',
            'started_at', 'submitted_at', 'expires_at',
            'time_remaining', 'duration_taken', 'is_expired', 'attempt_number',
        ]
        read_only_fields = [
            'id', 'score', 'points_earned', 'passed',
            'started_at', 'submitted_at', 'expires_at', 'attempt_number',
        ]


# ───────────────────────────────────────────────────
#  ExamResult Serializer (للطالب بعد التسليم)
# ───────────────────────────────────────────────────
class ExamResultSerializer(ExamAttemptSerializer):
    student_answers      = serializers.SerializerMethodField()

    def get_student_answers(self, obj):
        return StudentAnswerSerializer(obj.student_answers.all(), many=True, context=self.context).data
    total_questions      = serializers.SerializerMethodField()
    total_points         = serializers.SerializerMethodField()
    correct_count        = serializers.SerializerMethodField()
    wrong_count          = serializers.SerializerMethodField()
    passing_score        = serializers.IntegerField(source='exam.passing_score', read_only=True)
    # إعدادات الامتحان — الفرونت يحتاجها يعرض الصفحة صح
    allow_review         = serializers.BooleanField(source='exam.allow_review',         read_only=True)
    show_correct_answers = serializers.BooleanField(source='exam.show_correct_answers', read_only=True)
    show_result_immediately = serializers.BooleanField(source='exam.show_result_immediately', read_only=True)

    class Meta(ExamAttemptSerializer.Meta):
        fields = ExamAttemptSerializer.Meta.fields + [
            'student_answers', 'total_questions', 'total_points',
            'correct_count', 'wrong_count', 'passing_score',
            'allow_review', 'show_correct_answers', 'show_result_immediately',
        ]

    def get_total_questions(self, obj): return obj.exam.total_questions
    def get_total_points(self, obj):    return obj.exam.total_points

    def get_correct_count(self, obj):
        return obj.student_answers.filter(is_correct=True).count()

    def get_wrong_count(self, obj):
        return obj.student_answers.filter(is_correct=False).count()


# ═══════════════════════════════════════════════════
#  Serializers للمدرب
# ═══════════════════════════════════════════════════

class AnswerWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Answer
        fields = ['id', 'answer_text', 'is_correct', 'order']


class QuestionWriteSerializer(serializers.ModelSerializer):
    answers = AnswerWriteSerializer(many=True, required=False)

    class Meta:
        model  = Question
        fields = ['id', 'question_text', 'question_type', 'image', 'points', 'order', 'explanation', 'answers']

    def to_internal_value(self, data):
        import json
        # لو في answers_json → نحوّل الـ data لـ dict عادي ونضيف الـ answers
        if 'answers_json' in data:
            try:
                parsed = json.loads(data['answers_json'])
                # نحوّل QueryDict → dict عادي علشان نقدر نتحكم فيه
                plain = {}
                for k in data:
                    val = data.getlist(k) if hasattr(data, 'getlist') else data[k]
                    if isinstance(val, list) and len(val) == 1:
                        val = val[0]
                    plain[k] = val
                plain['answers'] = parsed
                data = plain
            except Exception:
                pass
        return super().to_internal_value(data)

    def create(self, validated_data):
        answers_data = validated_data.pop('answers', [])
        question = Question.objects.create(**validated_data)
        for i, ans in enumerate(answers_data):
            ans['order'] = ans.get('order', i)
            Answer.objects.create(question=question, **ans)
        return question

    def update(self, instance, validated_data):
        answers_data = validated_data.pop('answers', None)
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()
        if answers_data is not None:
            instance.answers.all().delete()
            for i, ans in enumerate(answers_data):
                ans['order'] = ans.get('order', i)
                Answer.objects.create(question=instance, **ans)
        return instance


class InstructorExamSerializer(serializers.ModelSerializer):
    questions       = serializers.SerializerMethodField()

    def get_questions(self, obj):
        return QuestionSerializer(obj.questions.all(), many=True, context=self.context).data
    total_questions = serializers.SerializerMethodField()
    total_points    = serializers.SerializerMethodField()
    attempts_count  = serializers.SerializerMethodField()
    course_title    = serializers.CharField(source='course.title', read_only=True)
    course_id       = serializers.IntegerField(source='course.id',   read_only=True)

    class Meta:
        model  = Exam
        fields = [
            'id', 'course', 'course_id', 'course_title',
            'title', 'description', 'instructions',
            'status', 'duration', 'passing_score', 'max_attempts',
            'shuffle_questions', 'shuffle_answers',
            'show_result_immediately', 'show_correct_answers', 'allow_review',
            'is_open', 'available_from', 'available_until',
            'total_questions', 'total_points', 'attempts_count',
            'created_at', 'updated_at', 'questions',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_total_questions(self, obj): return obj.questions.count()
    def get_total_points(self, obj):    return sum(q.points for q in obj.questions.all())
    def get_attempts_count(self, obj):  return obj.attempts.exclude(status='in_progress').count()

    def validate_course(self, value):
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            if value.instructor != request.user:
                raise serializers.ValidationError("هذا الكورس لا يخصك")
        return value


class InstructorAttemptSerializer(serializers.ModelSerializer):
    student_name    = serializers.SerializerMethodField()
    student_email   = serializers.SerializerMethodField()
    exam_title      = serializers.CharField(source='exam.title', read_only=True)
    correct_count   = serializers.SerializerMethodField()
    wrong_count     = serializers.SerializerMethodField()
    total_questions = serializers.SerializerMethodField()
    duration_taken  = serializers.SerializerMethodField()
    student_answers = serializers.SerializerMethodField()

    def get_student_answers(self, obj):
        return StudentAnswerSerializer(obj.student_answers.all(), many=True, context=self.context).data

    class Meta:
        model  = ExamAttempt
        fields = [
            'id', 'student_name', 'student_email', 'exam_title',
            'status', 'score', 'points_earned', 'passed',
            'started_at', 'submitted_at', 'attempt_number',
            'correct_count', 'wrong_count', 'total_questions',
            'duration_taken', 'student_answers',
        ]

    def get_student_name(self, obj):    return obj.student.user.get_full_name() or obj.student.user.username
    def get_student_email(self, obj):   return obj.student.user.email
    def get_correct_count(self, obj):   return obj.student_answers.filter(is_correct=True).count()
    def get_wrong_count(self, obj):     return obj.student_answers.filter(is_correct=False).count()
    def get_total_questions(self, obj): return obj.exam.total_questions
    def get_duration_taken(self, obj):  return obj.duration_taken
