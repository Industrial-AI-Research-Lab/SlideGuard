"""
Translation system for SlideGuard UI
Supports English (en) and Russian (ru) languages
"""

TRANSLATIONS = {
    "en": {
        # Main title and description
        "app_title": "SlideGuard - AI-Powered Presentation Evaluation",
        "app_description": "Upload your presentation PDF, select evaluation criteria, and get detailed feedback on your slides.",
        
        # Upload section
        "upload_section": "📁 Upload Presentation",
        "upload_label": "Upload PDF Presentation",
        
        # Presentation type selection
        "presentation_type_md": "📋 Select Presentation Type",
        "presentation_type_label": "Presentation Type",
        "presentation_type_scientific": "Scientific",
        "presentation_type_industrial": "Industrial",
        "presentation_type_collaborative": "Collaborative",
        "presentation_type_technological": "Technological",
        "presentation_type_required": "Please select a presentation type.",
        "invalid_presentation_type": "Invalid presentation type selected.",
        
        # Criteria selection
        "criteria_section": "🎯 Select Evaluation Criteria",
        "slide_criteria_label": "Slide criteria",
        "deck_criteria_label": "Deck criteria",
        "criteria_validation_error": "Please select at least one criteria.",
        "criteria_language_label": "Criteria language",
        "criteria_language_en": "English",
        "criteria_language_ru": "Russian",
        
        # Buttons
        "start_evaluation": "🚀 Start Evaluation",
        "evaluating": "⏳ Evaluating...",
        "generate_report": "📄 Generate PDF Report",
        "download_report": "Download PDF Report",
        "previous_slide": "◀️ Previous",
        "next_slide": "Next ▶️",
        "refresh": "Refresh",
        "logout": "Logout",
        
        # Results section
        "results_section": "📊 Evaluation Results",
        "status_label": "Status",
        "current_slide_label": "Current Slide",
        
        # Tab names
        "tab_viewer": "🖼️ Interactive Presentation Viewer",
        "tab_deck": "📋 Deck-Level Results",
        "tab_admin": "🔒 Admin Panel",
        "slide_preview_label": "Slide Preview",
        
        # Admin panel
        "admin_tab_users": "Users",
        "admin_tab_create": "Create User",
        "admin_tab_manage": "Manage User",
        "admin_username": "Username",
        "admin_password": "Password",
        "admin_role": "Role",
        "admin_register": "Register User",
        "admin_status": "Status",
        "admin_select_user": "Select User",
        "admin_new_role": "New Role",
        "admin_update_role": "Update Role",
        "admin_new_password": "New Password",
        "admin_update_password": "Update Password",
        "admin_confirm_delete": "Confirm Delete",
        "admin_delete_user": "Delete User",
        "admin_action_status": "Action Status",
        "admin_not_authorized": "Not authorized",
        "admin_fields_required": "Username and password are required",
        "admin_user_registered": "User registered successfully",
        "admin_user_exists": "User already exists",
        "admin_select_user_role": "Select user and role",
        "admin_cannot_change_own": "Cannot change own role",
        "admin_role_updated": "Role updated",
        "admin_user_not_found": "User not found",
        "admin_set_password": "Select user and set password",
        "admin_password_empty": "Password cannot be empty",
        "admin_password_updated": "Password updated",
        "admin_select_user_delete": "Select user",
        "admin_confirm_delete_msg": "Confirm delete",
        "admin_cannot_delete_self": "Cannot delete self",
        "admin_user_deleted": "User deleted",
        
        # Status messages
        "processing": "🔄 Processing evaluation... Please wait.",
        "upload_prompt": "Upload a presentation to launch evaluation.",
        "upload_prompt_slides": "Upload a presentation to see slide evaluations.",
        "evaluation_success": "✅ Evaluation completed successfully! Processed {slides} slides with {slide_criteria} slide criteria and {deck_criteria} deck criteria.",
        "evaluation_failed": "❌ Evaluation failed: {error}",
        "no_pdf": "Please upload a PDF file to start evaluation.",
        "evaluator_not_initialized": "Evaluator not initialized. Please check your configuration.",
        "failed_extract": "Failed to extract slides.",
        
        # Report generation
        "report_success": "✅ PDF report generated successfully! Click the download button to save it.",
        "report_failed": "❌ Failed to generate PDF report: {error}",
        "no_evaluation": "❌ No evaluation available. Please run an evaluation first.",
        
        # Evaluation results
        "deck_results_title": "📋 Deck-Level Evaluation Results",
        "slide_results_title": "📄 Slide-Level Evaluation Results",
        "slide_evaluation_title": "📊 Slide {number} Evaluation",
        "no_deck_evaluations": "No deck-level evaluations available.",
        "no_slide_evaluations": "No slide-level evaluations available.",
        "no_slide_evaluation_single": "⚠️ No evaluations available for this slide.",
        "no_detailed_results": "No detailed evaluation results available.\n\n",
        
        # Score indicators
        "score_label": "📊 Score:",
        "overall_score_label": "🏆 Overall Score:",
        "assessment_label": "Assessment:",
        "excellent": "Excellent",
        "good": "Good",
        "fair": "Fair",
        "needs_improvement": "Needs Improvement",
        "comments": "💬 Comments:",
        "recommendations": "💡 Recommendations:",
        "tldr": "⚡ TL;DR",
        "summary": "📝 Summary",
        
        # Severity indicators
        "priority_label": "Priority:",
        "low_priority": "Low Priority",
        "medium_priority": "Medium Priority",
        "high_priority": "High Priority",
        "info": "Info",
        "severity_label": "Severity:",
        "evaluation_label": "📝 Evaluation:",
        "suggestion_label": "💡 Suggestion:",
        "total_severity": "📊 Total Severity:",
        "overall_assessment": "Overall Assessment:",
        "analysis": "Analysis",
        
        # PDF Report
        "report_title": "SlideGuard AI Evaluation Report",
        "report_presentation": "Presentation:",
        "report_date": "Evaluation Date:",
        "report_total_slides": "Total Slides:",
        "report_tldr": "TL;DR",
        "report_summary": "Summary",
        "report_deck_title": "Deck-Level Evaluation Results",
        "report_slide_title": "Slide-Level Evaluation Results",
        "report_slide": "Slide",
        "report_no_evaluations": "No evaluations available for this slide.",
        "report_generated": "Generated on",
        "report_page": "Page",
    },
    "ru": {
        # Main title and description
        "app_title": "SlideGuard - ИИ-оценка презентаций",
        "app_description": "Загрузите PDF-презентацию, выберите критерии оценки и получите подробную обратную связь по слайдам.",
        
        # Upload section
        "upload_section": "📁 Загрузка презентации",
        "upload_label": "Загрузить PDF-презентацию",
        
        # Presentation type selection
        "presentation_type_md": "📋 Выбор типа презентации",
        "presentation_type_label": "Тип презентации",
        "presentation_type_scientific": "Научный",
        "presentation_type_industrial": "Индустриальный",
        "presentation_type_collaborative": "Коллаборативный",
        "presentation_type_technological": "Технологический",
        "presentation_type_required": "Пожалуйста, выберите тип презентации.",
        "invalid_presentation_type": "Выбран неверный тип презентации.",
        
        # Criteria selection
        "criteria_section": "🎯 Выбор критериев оценки",
        "slide_criteria_label": "Критерии слайдов",
        "deck_criteria_label": "Критерии презентации",
        "criteria_validation_error": "Пожалуйста, выберите хотя бы один критерий.",
        "criteria_language_label": "Язык критериев",
        "criteria_language_en": "Английский",
        "criteria_language_ru": "Русский",
        
        # Buttons
        "start_evaluation": "🚀 Начать оценку",
        "evaluating": "⏳ Оценка...",
        "generate_report": "📄 Создать PDF-отчет",
        "download_report": "Скачать PDF-отчет",
        "previous_slide": "◀️ Предыдущий",
        "next_slide": "Следующий ▶️",
        "refresh": "Обновить",
        "logout": "Выход",
        
        # Results section
        "results_section": "📊 Результаты оценки",
        "status_label": "Статус",
        "current_slide_label": "Текущий слайд",
        
        # Tab names
        "tab_viewer": "🖼️ Интерактивный просмотр презентации",
        "tab_deck": "📋 Результаты по презентации",
        "tab_admin": "🔒 Панель администратора",
        "slide_preview_label": "Предпросмотр слайда",
        
        # Admin panel
        "admin_tab_users": "Пользователи",
        "admin_tab_create": "Создать пользователя",
        "admin_tab_manage": "Управление пользователями",
        "admin_username": "Имя пользователя",
        "admin_password": "Пароль",
        "admin_role": "Роль",
        "admin_register": "Зарегистрировать пользователя",
        "admin_status": "Статус",
        "admin_select_user": "Выберите пользователя",
        "admin_new_role": "Новая роль",
        "admin_update_role": "Обновить роль",
        "admin_new_password": "Новый пароль",
        "admin_update_password": "Обновить пароль",
        "admin_confirm_delete": "Подтвердить удаление",
        "admin_delete_user": "Удалить пользователя",
        "admin_action_status": "Статус действия",
        "admin_not_authorized": "Недостаточно прав",
        "admin_fields_required": "Необходимы имя пользователя и пароль",
        "admin_user_registered": "Пользователь успешно зарегистрирован",
        "admin_user_exists": "Пользователь уже существует",
        "admin_select_user_role": "Выберите пользователя и роль",
        "admin_cannot_change_own": "Нельзя изменить свою роль",
        "admin_role_updated": "Роль обновлена",
        "admin_user_not_found": "Пользователь не найден",
        "admin_set_password": "Выберите пользователя и установите пароль",
        "admin_password_empty": "Пароль не может быть пустым",
        "admin_password_updated": "Пароль обновлен",
        "admin_select_user_delete": "Выберите пользователя",
        "admin_confirm_delete_msg": "Подтвердите удаление",
        "admin_cannot_delete_self": "Нельзя удалить себя",
        "admin_user_deleted": "Пользователь удален",
        
        # Status messages
        "processing": "🔄 Обработка оценки... Пожалуйста, подождите.",
        "upload_prompt": "Загрузите презентацию для начала оценки.",
        "upload_prompt_slides": "Загрузите презентацию для просмотра оценки слайдов.",
        "evaluation_success": "✅ Оценка завершена успешно! Обработано слайдов: {slides}, критериев слайдов: {slide_criteria}, критериев презентации: {deck_criteria}.",
        "evaluation_failed": "❌ Ошибка оценки: {error}",
        "no_pdf": "Пожалуйста, загрузите PDF-файл для начала оценки.",
        "evaluator_not_initialized": "Оценщик не инициализирован. Пожалуйста, проверьте конфигурацию.",
        "failed_extract": "Не удалось извлечь слайды.",
        
        # Report generation
        "report_success": "✅ PDF-отчет успешно создан! Нажмите кнопку загрузки, чтобы сохранить его.",
        "report_failed": "❌ Не удалось создать PDF-отчет: {error}",
        "no_evaluation": "❌ Оценка недоступна. Пожалуйста, сначала запустите оценку.",
        
        # Evaluation results
        "deck_results_title": "📋 Результаты оценки презентации",
        "slide_results_title": "📄 Результаты оценки слайдов",
        "slide_evaluation_title": "📊 Оценка слайда {number}",
        "no_deck_evaluations": "Нет доступных оценок презентации.",
        "no_slide_evaluations": "Нет доступных оценок слайдов.",
        "no_slide_evaluation_single": "⚠️ Нет доступных оценок для этого слайда.",
        "no_detailed_results": "Подробные результаты оценки недоступны.\n\n",
        
        # Score indicators
        "score_label": "📊 Оценка:",
        "overall_score_label": "🏆 Общая оценка:",
        "assessment_label": "Заключение:",
        "excellent": "Отлично",
        "good": "Хорошо",
        "fair": "Удовлетворительно",
        "needs_improvement": "Требует улучшения",
        "comments": "💬 Комментарии:",
        "recommendations": "💡 Рекомендации:",
        "tldr": "⚡ Краткая выжимка",
        "summary": "📝 Резюме",
        
        # Severity indicators
        "priority_label": "Приоритет:",
        "low_priority": "Низкий приоритет",
        "medium_priority": "Средний приоритет",
        "high_priority": "Высокий приоритет",
        "info": "Информация",
        "severity_label": "Серьезность:",
        "evaluation_label": "📝 Оценка:",
        "suggestion_label": "💡 Предложение:",
        "total_severity": "📊 Общая серьезность:",
        "overall_assessment": "Общее заключение:",
        "analysis": "Анализ",
        
        # PDF Report
        "report_title": "Отчет SlideGuard об оценке презентации",
        "report_presentation": "Презентация:",
        "report_date": "Дата оценки:",
        "report_total_slides": "Всего слайдов:",
        "report_tldr": "Краткая выжимка",
        "report_summary": "Резюме",
        "report_deck_title": "Результаты оценки презентации",
        "report_slide_title": "Результаты оценки слайдов",
        "report_slide": "Слайд",
        "report_no_evaluations": "Нет доступных оценок для этого слайда.",
        "report_generated": "Создано",
        "report_page": "Страница",
    }
}


def get_translation(key: str, lang: str = "en", **kwargs) -> str:
    """
    Get translated string for the given key and language.
    
    Args:
        key: Translation key
        lang: Language code ('en' or 'ru')
        **kwargs: Format parameters for string formatting
    
    Returns:
        Translated and formatted string
    """
    lang = lang if lang in TRANSLATIONS else "en"
    text = TRANSLATIONS[lang].get(key, TRANSLATIONS["en"].get(key, key))
    
    # Apply formatting if kwargs provided
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError:
            pass  # Return unformatted if keys don't match
    
    return text


class Translator:
    """Helper class for managing translations in UI components."""
    
    def __init__(self, lang: str = "en"):
        self.lang = lang
    
    def set_language(self, lang: str):
        """Set the current language."""
        self.lang = lang if lang in TRANSLATIONS else "en"
    
    def t(self, key: str, **kwargs) -> str:
        """Translate a key with the current language."""
        return get_translation(key, self.lang, **kwargs)
    
    def get_score_text(self, score_percentage: float) -> str:
        """Get assessment text based on score percentage."""
        if score_percentage >= 80:
            return self.t("excellent")
        elif score_percentage >= 60:
            return self.t("good")
        elif score_percentage >= 40:
            return self.t("fair")
        else:
            return self.t("needs_improvement")
    
    def get_priority_text(self, severity: int) -> str:
        """Get priority text based on severity level."""
        if severity == 1:
            return self.t("low_priority")
        elif severity == 2:
            return self.t("medium_priority")
        elif severity == 3:
            return self.t("high_priority")
        else:
            return self.t("info")

