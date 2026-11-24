# Commandes pip à exécuter : Aucune dépendance externe requise

import os
import sys
from typing import Any, Dict, List, Set, Tuple

from doc_anonymizer.audit_review_service import AuditReviewService
from doc_anonymizer.chat_filter_manager import ChatFilterManager
from doc_anonymizer.contact_csv_importer import ContactCatalogImporter
from doc_anonymizer.deanonymizer import DocumentDeanonymizer
from doc_anonymizer.duplicate_files_manager import DuplicateFilesManager
from doc_anonymizer.linked_sources_manager import LinkedSourcesManager
from doc_anonymizer.sms_filter_manager import SmsFilterManager
from doc_anonymizer.workspace_manager import WorkspaceManager


class AnonymizerGuiController:
    """Façade orchestrant dossiers, liens, contacts, SMS, chats, doublons et audit."""

    AI_PROMPT_TEMPLATES: List[Tuple[str, str]] = [
        (
            "1. Dossier médical / MDPH / Santé (chronologie & retentissement)",
            "Tu es un assistant spécialisé en droit médico-social (MDPH, handicap, santé).\n"
            "Analyse les pièces anonymisées ci-dessous et fournis :\n"
            "1) Une frise chronologique détaillée des faits médicaux, bilans et suivis.\n"
            "2) Les difficultés fonctionnelles et besoins de compensation mis en évidence.\n"
            "3) Les incohérences ou pièces manquantes à compléter.\n"
            "4) En conclusion, la liste exacte des fichiers sources utiles (# SOURCE TRANSCRIPTION : ...).",
        ),
        (
            "2. Prud'hommes / Droit du travail (faits, alertes & manquements)",
            "Tu es un assistant spécialisé en droit du travail français.\n"
            "Analyse les échanges et documents anonymisés ci-dessous et dresse :\n"
            "1) La chronologie précise des faits, alertes et décisions de l'employeur.\n"
            "2) Les éléments matériels caractérisant d'éventuels manquements (santé, sécurité, harcèlement, salaire).\n"
            "3) Les points à clarifier ou pièces complémentaires à réunir.\n"
            "4) En conclusion, la liste exacte des fichiers sources utiles (# SOURCE TRANSCRIPTION : ...).",
        ),
        (
            "3. Affaires familiales / Protection de l'enfance (JAF / juge des enfants)",
            "Tu es un assistant spécialisé en droit de la famille et protection de l'enfance.\n"
            "Synthétise objectivement les pièces anonymisées ci-dessous en mettant en avant :\n"
            "1) La chronologie des événements concernant l'enfant et l'organisation familiale.\n"
            "2) Les faits objectifs relatifs à l'intérêt supérieur de l'enfant, sa santé et sa scolarité.\n"
            "3) En conclusion, la liste exacte des fichiers sources utiles (# SOURCE TRANSCRIPTION : ...).",
        ),
        (
            "4. Contentieux civil / locatif / consommation (chronologie & preuves)",
            "Analyse de manière factuelle et neutre les documents anonymisés ci-dessous :\n"
            "1) Chronologie des engagements, incidents, relances et mises en demeure.\n"
            "2) Tableau des sommes, préjudices et justificatifs associés.\n"
            "3) En conclusion, la liste exacte des fichiers sources utiles (# SOURCE TRANSCRIPTION : ...).",
        ),
        (
            "5. Détection des contradictions et chronologie comparative",
            "Compare l'ensemble des déclarations, courriels, SMS et comptes rendus anonymisés ci-dessous.\n"
            "Relève uniquement les faits datés, les contradictions factuelles entre versions et les questions clés à poser.\n"
            "Termine par la liste exacte des fichiers sources pertinents (# SOURCE TRANSCRIPTION : ...).",
        ),
        (
            "6. Synthèse neutre et structurée (tous dossiers)",
            "Rédige une synthèse claire, neutre et structurée des documents anonymisés ci-dessous :\n"
            "1) Résumé exécutif en 10 lignes.\n"
            "2) Chronologie complète des événements datés.\n"
            "3) Liste exacte des fichiers sources les plus probants (# SOURCE TRANSCRIPTION : ...).",
        ),
    ]

    def __init__(self, root_dir: str) -> None:
        self.root_dir: str = os.path.abspath(root_dir)
        self.ws_manager: WorkspaceManager = WorkspaceManager(self.root_dir)
        self.workspaces_base_dir: str = self.ws_manager.workspaces_base_dir
        self.contacts_script: str = os.path.join(self.root_dir, "run_contacts.py")
        self.main_script: str = os.path.join(self.root_dir, "run_documents.py")
    def list_workspaces(self) -> List[Tuple[str, str]]:
        return self.ws_manager.list_workspaces()

    def get_last_opened_workspace(self) -> str:
        return self.ws_manager.get_last_opened_workspace()

    def save_last_opened_workspace(self, ini_path: str) -> None:
        self.ws_manager.save_last_opened_workspace(ini_path)

    def create_workspace(self, workspace_name: str) -> str:
        return self.ws_manager.create_workspace(workspace_name)

    def resolve_workspace_paths(self, ini_path: str) -> Dict[str, str]:
        return self.ws_manager.resolve_workspace_paths(ini_path)

    def _linked_manager(self, ini_path: str) -> LinkedSourcesManager:
        return LinkedSourcesManager(self.resolve_workspace_paths(ini_path)["workspace_root"])

    def _contact_importer(self, ini_path: str) -> ContactCatalogImporter:
        return ContactCatalogImporter(self.resolve_workspace_paths(ini_path), ini_path)

    def _sms_manager(self, ini_path: str) -> SmsFilterManager:
        return SmsFilterManager(self.resolve_workspace_paths(ini_path), self._contact_importer(ini_path))

    def _chat_manager(self, ini_path: str) -> ChatFilterManager:
        return ChatFilterManager(self.resolve_workspace_paths(ini_path), self._contact_importer(ini_path))

    def _duplicates_manager(self, ini_path: str) -> DuplicateFilesManager:
        return DuplicateFilesManager(self.resolve_workspace_paths(ini_path))

    def load_duplicate_file_items(self, ini_path: str) -> List[Dict[str, Any]]:
        return self._duplicates_manager(ini_path).find_duplicate_items()

    def save_duplicate_file_selection(self, ini_path: str, items: List[Dict[str, Any]]) -> Tuple[int, int]:
        return self._duplicates_manager(ini_path).save_selection(items)

    def list_linked_sources(self, ini_path: str) -> List[Dict[str, str]]:
        return self._linked_manager(ini_path).load_links()

    def inspect_storage_location(self, ini_path: str, target_path: str) -> Tuple[bool, str]:
        ws_root: str = self.resolve_workspace_paths(ini_path)["workspace_root"]
        return LinkedSourcesManager.classify_storage_location(target_path, ws_root)

    def register_or_copy_sources(self, ini_path: str, paths_list: List[str], copy_external: bool = False) -> Tuple[int, int]:
        paths = self.resolve_workspace_paths(ini_path)
        mgr = self._linked_manager(ini_path)
        added_links = copied_local = 0
        for p in paths_list:
            is_ext, lbl = LinkedSourcesManager.classify_storage_location(p, paths["workspace_root"])
            if is_ext and copy_external:
                copied_local += mgr.copy_paths_into_directory([p], paths["sources_dir"])
            else:
                added_links += mgr.add_links([p], storage_label=lbl)
        return added_links, copied_local

    def expand_linked_files(self, ini_path: str) -> Tuple[List[str], List[str]]:
        return self._linked_manager(ini_path).expand_linked_files(set())

    def remove_linked_source(self, ini_path: str, target_path: str) -> bool:
        return self._linked_manager(ini_path).remove_link(target_path)

    def import_contacts_csv(self, ini_path: str, source_file: str) -> str:
        return self._contact_importer(ini_path).import_contact_file(source_file)

    def list_contact_csv_files(self, ini_path: str) -> List[str]:
        return self._contact_importer(ini_path).list_contact_files()

    def load_contact_filter_items(self, ini_path: str) -> List[Dict[str, Any]]:
        return self._contact_importer(ini_path).load_filter_items()

    def save_contact_filter_selection(self, ini_path: str, items: List[Dict[str, Any]]) -> int:
        return self._contact_importer(ini_path).save_filter_selection(items)

    def list_sms_export_files(self, ini_path: str) -> List[str]:
        return self._sms_manager(ini_path).list_export_files()

    def load_sms_number_filter_items(self, ini_path: str) -> List[Dict[str, Any]]:
        return self._sms_manager(ini_path).load_number_filter_items()

    def save_sms_number_filter_selection(self, ini_path: str, items: List[Dict[str, Any]]) -> int:
        return self._sms_manager(ini_path).save_number_filter_selection(items)

    def list_chat_export_files(self, ini_path: str) -> List[str]:
        return self._chat_manager(ini_path).list_export_files()

    def load_chat_conversation_filter_items(self, ini_path: str) -> List[Dict[str, Any]]:
        return self._chat_manager(ini_path).load_conversation_filter_items()

    def save_chat_conversation_filter_selection(self, ini_path: str, items: List[Dict[str, Any]]) -> int:
        return self._chat_manager(ini_path).save_conversation_filter_selection(items)

    def list_archived_ai_files(self, ini_path: str) -> List[str]:
        archive_dir: str = os.path.join(self.resolve_workspace_paths(ini_path)["workspace_root"], "retour_ia_brut")
        if not os.path.isdir(archive_dir):
            return []
        return [os.path.abspath(os.path.join(archive_dir, fn)) for fn in sorted(os.listdir(archive_dir)) if not fn.startswith(".") and os.path.isfile(os.path.join(archive_dir, fn))]

    def archive_ai_input_files(self, ini_path: str, file_paths: List[str]) -> List[str]:
        archive_dir: str = os.path.join(self.resolve_workspace_paths(ini_path)["workspace_root"], "retour_ia_brut")
        return [DocumentDeanonymizer.archive_input_file(fp, archive_dir) for fp in file_paths if os.path.isfile(fp)]

    def analyze_ai_files_for_deanonymization(self, ini_path: str, file_paths: List[str]) -> Tuple[List[Dict[str, Any]], str, List[str]]:
        deanonymizer = DocumentDeanonymizer(self.resolve_workspace_paths(ini_path))
        archived_files: List[str] = self.archive_ai_input_files(ini_path, file_paths)
        merged_text: str = "\n\n".join(DocumentDeanonymizer.read_document_text(fp) for fp in archived_files if os.path.isfile(fp))
        return deanonymizer.analyze_text(merged_text), merged_text, archived_files

    def export_deanonymized_ai_files(self, ini_path: str, file_paths: List[str], proposals: List[Dict[str, Any]]) -> Tuple[List[str], str]:
        out_dir: str = os.path.join(self.resolve_workspace_paths(ini_path)["workspace_root"], "retour_ia_nominatif")
        exported: List[str] = [DocumentDeanonymizer.export_deanonymized_file(fp, out_dir, proposals) for fp in file_paths if os.path.isfile(fp)]
        return exported, out_dir

    def detect_zip_files(self, ini_path: str) -> List[str]:
        return self.ws_manager.detect_zip_files(ini_path)

    def build_cli_command(self, ini_path: str, mode: str) -> List[str]:
        abs_ini: str = os.path.abspath(ini_path)
        if mode == "contacts":
            return [sys.executable, self.contacts_script, "-c", abs_ini]
        cmd: List[str] = [sys.executable, self.main_script, "-c", abs_ini]
        if mode == "extract_only":
            cmd.append("--extract-only")
        elif mode == "anonymize_only":
            cmd.append("--anonymize-only")
        elif mode == "reset_anonymize_only":
            cmd.extend(["--anonymize-only", "--reset-results"])
        elif mode == "full_with_contacts":
            cmd.append("--with-contacts")
        return cmd

    def auto_organize_dropped_files(self, ini_path: str) -> Tuple[int, int]:
        return self.ws_manager.auto_organize_dropped_files(ini_path)

    def load_dashboard_stats(self, ini_path: str) -> Dict[str, Any]:
        return AuditReviewService.load_dashboard_stats(self.resolve_workspace_paths(ini_path))

    def load_audit_candidates(self, ini_path: str) -> List[Tuple[str, str]]:
        return AuditReviewService.load_audit_candidates(self.resolve_workspace_paths(ini_path))

    def load_audit_occurrences(self, ini_path: str, candidate: str) -> List[Dict[str, str]]:
        return AuditReviewService.load_audit_occurrences(self.resolve_workspace_paths(ini_path), candidate)

    def approve_audit_mask(self, ini_path: str, candidate: str, alias: str) -> None:
        AuditReviewService.approve_audit_mask(self.resolve_workspace_paths(ini_path), candidate, alias)

    def exclude_audit_false_positive(self, ini_path: str, candidate: str) -> None:
        AuditReviewService.exclude_audit_false_positive(self.resolve_workspace_paths(ini_path), candidate)

    def resolve_ai_selected_extracted_files(self, ini_path: str, raw_ai_text: str) -> Set[str]:
        return AuditReviewService.resolve_ai_selected_extracted_files(self.resolve_workspace_paths(ini_path), raw_ai_text)
