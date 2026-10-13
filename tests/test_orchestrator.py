import unittest
from unittest.mock import Mock

from igris_os.ai.orchestrator import ModelOrchestrator, ModelPurpose
from igris_os.ai.ollama import ModelReply
from igris_os.application.coordinator import SpecialistCoordinator
from igris_os.programming.specialists import SpecialistRegistry, SpecialistRole


class ModelOrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.models = (
            "llama3.1:8b",
            "nomic-embed-text:latest",
            "qwen2.5-coder:1.5b",
            "qwen3.5:4b",
            "qwen2.5-coder:7b",
            "deepseek-r1:32b",
            "deepseek-r1:8b",
            "kimi-k3:cloud",
        )
        self.client = Mock()
        self.client.models.return_value = self.models
        self.router = ModelOrchestrator(self.client)

    def test_routes_programming_to_coder(self):
        route = self.router.route(ModelPurpose.PROGRAMMING)
        self.assertEqual(route.model, "qwen2.5-coder:7b")
        self.assertIn("programacion", route.reason)

    def test_routes_reasoning_to_deepseek_8b_not_32b(self):
        route = self.router.route(ModelPurpose.REASONING)
        self.assertEqual(route.model, "deepseek-r1:8b")
        self.assertNotIn("deepseek-r1:32b", route.considered)

    def test_routes_general_chat_prefers_light_instruct_model(self):
        route = self.router.route(ModelPurpose.GENERAL)
        # Chat: instruct ligero primero (qwen3.5:4b); los modelos "-base" no
        # estan instruidos y nunca son candidatos. 7B queda reservado para
        # programacion y razonamiento (seleccion dinamica).
        self.assertEqual(route.model, "qwen3.5:4b")
        self.assertNotIn("base", route.model)

    def test_routes_dynamic_selection_by_task(self):
        # El mismo enrutador elige el instruct ligero para chat y 7B para
        # programacion: la eleccion es dinamica por tarea, no unico fijo.
        general = self.router.route(ModelPurpose.GENERAL)
        programming = self.router.route(ModelPurpose.PROGRAMMING)
        self.assertEqual(general.model, "qwen3.5:4b")
        self.assertEqual(programming.model, "qwen2.5-coder:7b")
        self.assertIn("programacion", programming.reason)

    def test_cloud_and_embedding_models_are_never_candidates(self):
        route = self.router.route(ModelPurpose.GENERAL)
        self.assertNotIn("kimi-k3:cloud", route.considered)
        self.assertNotIn("nomic-embed-text:latest", route.considered)

    def test_remote_fallback_requires_explicit_opt_in_and_no_safe_local_model(self):
        from unittest.mock import patch
        self.client.models.return_value = ("moonshot/kimi-k3",)
        low_memory = {"ram_free_gb": 0.5, "vram_free_gb": 0.0, "uncertain": False}
        with patch.dict("os.environ", {"IGRIS_ALLOW_CLOUD_MODELS": "0"}):
            with patch("igris_os.ai.resources.get_system_resources", return_value=low_memory):
                disabled = self.router.route(ModelPurpose.PROGRAMMING)
        self.assertEqual(disabled.model, "")

        with patch.dict("os.environ", {"IGRIS_ALLOW_CLOUD_MODELS": "1"}):
            with patch("igris_os.ai.resources.get_system_resources", return_value=low_memory):
                enabled = self.router.route(ModelPurpose.PROGRAMMING)
        self.assertEqual(enabled.model, "moonshot/kimi-k3")
        self.assertEqual(enabled.backend, "moonshot")
        self.assertEqual(enabled.resources["execution_scope"], "external")
        self.assertIn("enviarán", enabled.resources["external_data_notice"])

    def test_remote_fallback_never_replaces_a_safe_local_model(self):
        from unittest.mock import patch
        self.client.models.return_value = ("qwen2.5-coder:1.5b", "moonshot/kimi-k3")
        self.client._backend_for.return_value = ("ollama", "http://127.0.0.1:11434")
        with patch.dict("os.environ", {"IGRIS_ALLOW_CLOUD_MODELS": "1"}):
            with patch("igris_os.ai.resources.get_system_resources", return_value={
                "ram_free_gb": 12.0, "vram_free_gb": 0.0, "uncertain": False,
            }):
                route = self.router.route(ModelPurpose.PROGRAMMING)
        self.assertEqual(route.model, "qwen2.5-coder:1.5b")
        self.assertEqual(route.backend, "ollama")
        self.assertNotEqual(route.resources.get("execution_scope"), "external")

    def test_external_openai_compatible_server_is_an_explicit_last_fallback(self):
        from unittest.mock import patch
        self.client.models.return_value = ("remote-openai/qwen-coder-large",)
        low_memory = {"ram_free_gb": 0.5, "vram_free_gb": 0.0, "uncertain": False}
        with patch.dict("os.environ", {
            "IGRIS_ALLOW_REMOTE_MODELS": "1", "IGRIS_ALLOW_CLOUD_MODELS": "0",
        }):
            with patch("igris_os.ai.resources.get_system_resources", return_value=low_memory):
                route = self.router.route(ModelPurpose.PROGRAMMING)
        self.assertEqual(route.model, "remote-openai/qwen-coder-large")
        self.assertEqual(route.backend, "remote-openai")
        self.assertEqual(route.resources["external_backend"], "remote-openai")
        self.assertEqual(route.resources["execution_scope"], "external")

    def test_reported_parameter_count_overrides_model_tag_limit(self):
        self.client.models.return_value = ("deepseek-r1:8b",)
        self.client.model_metadata.return_value = {
            "details": {"parameter_size": "8.2B"},
        }
        self.assertEqual(self.router.available_models(), ())

    def test_fails_clearly_when_no_local_model_is_usable(self):
        route = self.router.route(
            ModelPurpose.REASONING,
            available=("deepseek-r1:32b", "kimi-k3:cloud", "nomic-embed-text:latest"),
        )
        self.assertEqual(route.model, "")
        self.assertIn("no hay un modelo local apto", route.reason)

    def test_infers_specialist_purpose_without_model_call(self):
        self.assertEqual(
            self.router.infer_purpose("Diseña la arquitectura y la hoja de ruta"),
            ModelPurpose.REASONING,
        )
        self.assertEqual(
            self.router.infer_purpose("Implementa esta función de Python", "programming"),
            ModelPurpose.PROGRAMMING,
        )
        self.assertEqual(
            self.router.infer_purpose("¿Qué tal va el proyecto?"),
            ModelPurpose.GENERAL,
        )

    def test_review_routes_to_a_different_model_family(self):
        route = self.router.route(ModelPurpose.REVIEW)
        self.assertEqual(route.model, "llama3.1:8b")

    def test_role_routing_separates_architecture_code_and_review(self):
        self.assertEqual(
            self.router.purpose_for_role("arquitecto"), ModelPurpose.REASONING)
        self.assertEqual(
            self.router.purpose_for_role("implementador_senior"), ModelPurpose.PROGRAMMING)
        self.assertEqual(
            self.router.purpose_for_role("revisor_independiente"), ModelPurpose.REVIEW)

    def test_specialist_coordinator_uses_local_model_pool_per_role(self):
        client = Mock()
        client.models.return_value = self.models
        client.generate.side_effect = lambda prompt, model: ModelReply(
            True, "resultado comprobable", model)
        coordinator = SpecialistCoordinator(client=client)

        result = coordinator.coordinate("Implementa una función Python y revisa el código", "qwen2.5-coder:7b")

        models_by_role = {finding.role: finding.model for finding in result.findings}
        self.assertEqual(models_by_role["arquitecto"], "deepseek-r1:8b")
        self.assertEqual(models_by_role["implementador_senior"], "qwen2.5-coder:7b")
        self.assertEqual(result.review.model, "llama3.1:8b")
    def test_low_memory_does_not_force_an_unsafe_model(self):
        from unittest.mock import patch
        with patch('igris_os.ai.resources.get_system_resources') as mock_sys:
            mock_sys.return_value = {"ram_free_gb": 0.5, "vram_free_gb": 0.0, "uncertain": False}
            route = self.router.route(ModelPurpose.PROGRAMMING, available=("qwen2.5-coder:7b", "qwen2.5-coder:1.5b"))
        self.assertEqual(route.model, "")
        self.assertIn("no se fuerza fallback", route.reason)
        self.assertIsNone(route.fallback)
        self.assertIsNotNone(route.resources)

    def test_ram_and_vram_are_not_added_as_one_pool(self):
        from unittest.mock import patch
        with patch('igris_os.ai.resources.get_system_resources', return_value={
            "ram_free_gb": 2.0, "vram_free_gb": 2.0, "uncertain": False,
        }):
            route = self.router.route(ModelPurpose.PROGRAMMING, available=("qwen2.5-coder:1.5b",))
        self.assertEqual(route.model, "")

    def test_small_fallback_is_selected_when_only_it_fits(self):
        from unittest.mock import patch
        with patch('igris_os.ai.resources.get_system_resources', return_value={
            "ram_free_gb": 5.0, "vram_free_gb": 3.0, "uncertain": False,
        }):
            route = self.router.route(ModelPurpose.PROGRAMMING, available=("qwen2.5-coder:7b", "qwen2.5-coder:1.5b"))
        self.assertEqual(route.model, "qwen2.5-coder:1.5b")
        self.assertEqual(route.fallback, "qwen2.5-coder:1.5b")

    def test_auditable_routing_decision(self):
        self.client._backend_for.return_value = ("ollama", "http://127.0.0.1:11434")
        route = self.router.route(ModelPurpose.REASONING)
        self.assertIsNotNone(route.resources)
        self.assertTrue(isinstance(route.resources, dict))
        self.assertIn("ram_free_gb", route.resources)
        self.assertIn("model_assessments", route.resources)
        self.assertEqual(route.backend, "ollama")

    def test_configured_preference_is_used_only_when_installed_and_safe(self):
        from unittest.mock import patch
        resources = {"ram_free_gb": 64.0, "vram_free_gb": None, "uncertain": True}
        with patch("igris_os.ai.resources.get_system_resources", return_value=resources):
            route = self.router.route(
                ModelPurpose.GENERAL,
                available=("llama3.1:8b", "qwen2.5-coder:7b"),
                preferred_model="qwen2.5-coder:7b",
            )
        self.assertEqual(route.model, "qwen2.5-coder:7b")
        self.assertIn("configurado", route.reason)

    def test_unavailable_configured_preference_falls_back_through_resource_router(self):
        from unittest.mock import patch
        with patch("igris_os.ai.resources.get_system_resources", return_value={
            "ram_free_gb": 64.0, "vram_free_gb": None, "uncertain": True,
        }):
            route = self.router.route(
                ModelPurpose.GENERAL, available=("llama3.1:8b",),
                preferred_model="custom-not-installed",
            )
        self.assertEqual(route.model, "llama3.1:8b")
        self.assertIn("ausente", route.reason)

    def test_configured_preference_cannot_bypass_memory_limit(self):
        from unittest.mock import patch
        with patch("igris_os.ai.resources.get_system_resources", return_value={
            "ram_free_gb": 0.5, "vram_free_gb": 0.0, "uncertain": False,
        }):
            route = self.router.route(
                ModelPurpose.GENERAL, available=("llama3.1:8b",),
                preferred_model="llama3.1:8b",
            )
        self.assertEqual(route.model, "")
        self.assertIn("no se fuerza fallback", route.reason)

    def test_repeated_role_routes_reuse_model_metadata(self):
        from unittest.mock import patch
        snapshot = {"ram_free_gb": 64.0, "vram_free_gb": None, "uncertain": True}
        with patch("igris_os.ai.resources.get_system_resources", return_value=snapshot) as read_resources:
            self.router.route(ModelPurpose.PROGRAMMING, resource_snapshot=snapshot)
            first_route_calls = self.client.model_metadata.call_count
            self.router.route(ModelPurpose.REVIEW, resource_snapshot=snapshot)
        read_resources.assert_not_called()
        # Un unico fetch por modelo local razonable (nomic/kimi se filtran sin
        # consultar) y la segunda ruta reutiliza la caché: cero refetch.
        self.assertLessEqual(first_route_calls, len(self.models))
        self.assertEqual(self.client.model_metadata.call_count, first_route_calls)

    def test_specialist_coordinator_does_not_bypass_an_unsafe_route(self):
        from unittest.mock import patch
        client = Mock()
        client.models.return_value = self.models
        with patch('igris_os.ai.resources.get_system_resources', return_value={
            "ram_free_gb": 0.5, "vram_free_gb": 0.0, "uncertain": False,
        }):
            result = SpecialistCoordinator(client=client).coordinate(
                "Implementa un programa Python", "qwen2.5-coder:7b")
        client.generate.assert_not_called()
        self.assertFalse(result.complete)
        self.assertTrue(all(not finding.ok for finding in result.findings))
        self.assertIn("memoria", result.review.route_reason)

    def test_specialist_registry_does_not_execute_an_unsafe_model(self):
        from unittest.mock import patch
        client = Mock()
        client.models.return_value = ("qwen2.5-coder:7b",)
        with patch("igris_os.ai.resources.get_system_resources", return_value={
            "ram_free_gb": 0.5, "vram_free_gb": 0.0, "uncertain": False,
        }):
            result = SpecialistRegistry(client).execute(
                SpecialistRole.PROGRAMMER, "Implementa el requisito")
        client.generate.assert_not_called()
        self.assertFalse(result.ok)
        self.assertIn("memoria", result.error)

    def test_language_test_prompts_use_available_offline_runners(self):
        from igris_os.programming.languages import Language
        from igris_os.programming.multilang import MultiLanguageCoordinator
        self.assertIn("node:test", MultiLanguageCoordinator.LANGUAGE_PROMPTS[Language.TYPESCRIPT])
        self.assertNotIn("Jest", MultiLanguageCoordinator.LANGUAGE_PROMPTS[Language.TYPESCRIPT])
        self.assertIn("test_runner.gd", MultiLanguageCoordinator.LANGUAGE_PROMPTS[Language.GDSCRIPT])

if __name__ == "__main__":
    unittest.main()
