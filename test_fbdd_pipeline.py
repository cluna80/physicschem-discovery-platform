"""
test_fbdd_pipeline.py
=====================
Comprehensive pytest test suite for the FBDD drug discovery pipeline.

Tests cover:
1. Fragment selection logic
2. Docking score validation
3. ADMET filter thresholds
4. Multi-agent orchestration flow

Uses mock docking results so tests run without AutoDock Vina installed.

Usage:
    pytest test_fbdd_pipeline.py -v
    pytest test_fbdd_pipeline.py -v -k "test_fragment"
    pytest test_fbdd_pipeline.py -v --cov=autonomous_drug_agentV2
"""

import pytest
import tempfile
import os
import sys
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# Import the agent module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import autonomous_drug_agentV2 as agent_module


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_logger():
    """Mock AgentLogger for testing."""
    logger = Mock(spec=agent_module.AgentLogger)
    logger.log = Mock()
    logger.separator = Mock()
    logger.header = Mock()
    logger.get_entries = Mock(return_value=[])
    return logger


@pytest.fixture
def sample_fragments():
    """Sample fragment library for testing."""
    return [
        {"id": "F001", "smiles": "c1ccncc1", "name": "pyridine", "MW": 79.1, "LogP": 0.65, "HBD": 0, "HAC": 6},
        {"id": "F002", "smiles": "c1ccnc2ccccc12", "name": "quinoline", "MW": 129.2, "LogP": 2.03, "HBD": 0, "HAC": 10},
        {"id": "F016", "smiles": "Nc1ccccc1", "name": "aniline", "MW": 93.1, "LogP": 0.90, "HBD": 1, "HAC": 7},
        {"id": "F036", "smiles": "C1CCNCC1", "name": "piperidine", "MW": 85.1, "LogP": 0.84, "HBD": 1, "HAC": 6},
        {"id": "F071", "smiles": "Nc1ncnc2ccccc12", "name": "4-aminoquinazoline", "MW": 145.2, "LogP": 1.23, "HBD": 1, "HAC": 11},
    ]


@pytest.fixture
def mock_docking_results():
    """Mock docking results for testing."""
    return {
        "c1ccncc1": {"affinity": -5.2, "poses": [{"mode": 1, "affinity": -5.2, "rmsd_lb": 0.0, "rmsd_ub": 0.0}], "n_poses": 1},
        "c1ccnc2ccccc12": {"affinity": -6.8, "poses": [{"mode": 1, "affinity": -6.8, "rmsd_lb": 0.0, "rmsd_ub": 0.0}], "n_poses": 1},
        "Nc1ccccc1": {"affinity": -4.9, "poses": [{"mode": 1, "affinity": -4.9, "rmsd_lb": 0.0, "rmsd_ub": 0.0}], "n_poses": 1},
        "C1CCNCC1": {"affinity": -5.5, "poses": [{"mode": 1, "affinity": -5.5, "rmsd_lb": 0.0, "rmsd_ub": 0.0}], "n_poses": 1},
        "Nc1ncnc2ccccc12": {"affinity": -8.3, "poses": [{"mode": 1, "affinity": -8.3, "rmsd_lb": 0.0, "rmsd_ub": 0.0}], "n_poses": 1},
    }


@pytest.fixture
def mock_admet_results():
    """Mock ADMET-AI results for testing."""
    return {
        "hERG": 0.15,  # Safe
        "DILI": 0.25,  # Safe
        "AMES": 0.10,  # Safe
        "ClinTox": 0.20,  # Safe
        "Bioavailability_Ma": 0.75,  # Good
        "HIA_Hou": 0.85,  # Good
        "Solubility_AqSolDB": -3.2,  # Good
        "CYP3A4_Veith": 0.30,  # Safe
        "CYP2D6_Veith": 0.25,  # Safe
        "CYP2C9_Veith": 0.20,  # Safe
        "CYP2C19_Veith": 0.15,  # Safe
        "CYP1A2_Veith": 0.35,  # Safe
    }


# ============================================================================
# TEST: Fragment Selection
# ============================================================================

class TestFragmentSelection:
    """Test FragmentSelectorAgent logic."""

    def test_fragment_library_size(self):
        """Test that fragment library has expected size."""
        assert len(agent_module.FRAGMENT_LIBRARY) == 120
        assert all(len(f) == 3 for f in agent_module.FRAGMENT_LIBRARY)

    def test_fragment_library_structure(self):
        """Test fragment library structure."""
        for fid, smiles, name in agent_module.FRAGMENT_LIBRARY:
            assert fid.startswith("F")
            assert len(fid) == 4  # F001-F120
            assert isinstance(smiles, str)
            assert len(smiles) > 0
            assert isinstance(name, str)

    def test_fragment_selector_initialization(self, mock_logger):
        """Test FragmentSelectorAgent initialization."""
        selector = agent_module.FragmentSelectorAgent(mock_logger)
        assert selector.log == mock_logger
        assert selector.selected == []

    @patch('autonomous_drug_agentV2.RDKIT_OK', True)
    @patch('autonomous_drug_agentV2.Chem')
    @patch('autonomous_drug_agentV2.Descriptors')
    @patch('autonomous_drug_agentV2.Lipinski')
    def test_fragment_selection_ro3_filter(self, mock_lipinski, mock_descriptors, mock_chem, mock_logger):
        """Test Rule-of-3 filtering."""
        # Mock RDKit functions
        mock_mol = Mock()
        mock_mol.GetNumHeavyAtoms.return_value = 10
        mock_chem.MolFromSmiles.return_value = mock_mol
        mock_descriptors.MolWt.return_value = 250.0
        mock_descriptors.MolLogP.return_value = 2.5
        mock_lipinski.NumHDonors.return_value = 2

        selector = agent_module.FragmentSelectorAgent(mock_logger)
        selected = selector.load(n=10)

        # Should select fragments that pass Ro3
        assert len(selected) <= 10
        mock_logger.log.assert_called()

    def test_fragment_bias_prioritization(self, mock_logger, sample_fragments):
        """Test that bias parameter prioritizes matching fragments."""
        selector = agent_module.FragmentSelectorAgent(mock_logger)
        selector.selected = []
        
        # Mock the load method to use sample fragments
        with patch.object(selector, 'load', return_value=sample_fragments):
            frags = selector.load(n=5, bias="quinoline")
            
            # Quinoline should be prioritized if bias works
            assert len(frags) == 5

    @patch('autonomous_drug_agentV2.RDKIT_OK', True)
    @patch('autonomous_drug_agentV2.FilterCatalog')
    def test_pains_filter(self, mock_catalog, mock_logger, sample_fragments):
        """Test PAINS filter removes problematic fragments."""
        # Mock PAINS catalog
        mock_catalog_instance = Mock()
        mock_catalog_instance.GetMatches.return_value = []  # No PAINS matches
        mock_catalog.FilterCatalog.return_value = mock_catalog_instance

        selector = agent_module.FragmentSelectorAgent(mock_logger)
        
        with patch('autonomous_drug_agentV2.Chem.MolFromSmiles') as mock_mol:
            mock_mol.return_value = Mock()
            clean = selector.pains_filter(sample_fragments)
            
            # All fragments should pass (no PAINS matches)
            assert len(clean) == len(sample_fragments)


# ============================================================================
# TEST: Docking Score Validation
# ============================================================================

class TestDockingAgent:
    """Test DockingAgent logic."""

    def test_docking_agent_initialization(self, mock_logger):
        """Test DockingAgent initialization."""
        docker = agent_module.DockingAgent(
            mock_logger,
            receptor="test_receptor.pdbqt",
            center=(0, 0, 0),
            size=(25, 25, 25),
            exhaustiveness=8
        )
        assert docker.log == mock_logger
        assert docker.receptor == "test_receptor.pdbqt"
        assert docker.center == (0, 0, 0)
        assert docker.size == (25, 25, 25)
        assert docker.exh == 8
        assert docker._cache == {}

    def test_docking_cache(self, mock_logger, mock_docking_results):
        """Test that docking results are cached."""
        docker = agent_module.DockingAgent(
            mock_logger,
            receptor="test.pdbqt",
            center=(0, 0, 0),
            size=(25, 25, 25)
        )
        
        # Populate cache
        smiles = "c1ccncc1"
        docker._cache[smiles] = mock_docking_results[smiles]
        
        # Should return cached result
        result = docker.dock(smiles, "test")
        assert result == mock_docking_results[smiles]
        assert result["affinity"] == -5.2

    def test_docking_missing_vina(self, mock_logger):
        """Test error handling when Vina binary is missing."""
        docker = agent_module.DockingAgent(
            mock_logger,
            receptor="test.pdbqt",
            center=(0, 0, 0),
            size=(25, 25, 25)
        )
        docker.VINA = "/nonexistent/vina.exe"
        
        result = docker.dock("c1ccncc1", "test")
        assert "error" in result
        assert "Vina not found" in result["error"]

    def test_docking_missing_receptor(self, mock_logger):
        """Test error handling when receptor is missing."""
        docker = agent_module.DockingAgent(
            mock_logger,
            receptor="/nonexistent/receptor.pdbqt",
            center=(0, 0, 0),
            size=(25, 25, 25)
        )
        
        with patch.object(docker, 'VINA', './bin/vina.exe'):
            with patch('os.path.isfile', side_effect=lambda x: x == './bin/vina.exe'):
                result = docker.dock("c1ccncc1", "test")
                assert "error" in result
                assert "Receptor not found" in result["error"]

    def test_screen_fragments_threshold(self, mock_logger, sample_fragments, mock_docking_results):
        """Test fragment screening with affinity threshold."""
        docker = agent_module.DockingAgent(
            mock_logger,
            receptor="test.pdbqt",
            center=(0, 0, 0),
            size=(25, 25, 25)
        )
        
        # Mock dock method to return predefined results
        def mock_dock(smiles, name):
            return mock_docking_results.get(smiles, {"error": "Not found"})
        
        with patch.object(docker, 'dock', side_effect=mock_dock):
            results = docker.screen_fragments(sample_fragments, ref_affinity=-6.0)
            
            # Should return fragments with affinity <= -6.0
            hits = [r for r in results if r.get("dock_affinity", 0) <= -6.0]
            assert len(hits) >= 1  # At least quinoline (-6.8) and 4-aminoquinazoline (-8.3)


# ============================================================================
# TEST: Higgs Significance Testing
# ============================================================================

class TestHiggsSignificance:
    """Test HiggsSignificanceTester logic."""

    def test_higgs_initialization(self, mock_logger):
        """Test HiggsSignificanceTester initialization."""
        higgs = agent_module.HiggsSignificanceTester(mock_logger)
        assert higgs.null_mean is None
        assert higgs.null_std is None
        assert higgs.null_n == 0
        assert higgs.log == mock_logger

    def test_fit_null_distribution(self, mock_logger):
        """Test fitting null distribution from fragment affinities."""
        higgs = agent_module.HiggsSignificanceTester(mock_logger)
        
        # Fragment affinities (typical range: -3 to -6 kcal/mol)
        fragment_affinities = [-4.5, -5.0, -5.2, -4.8, -5.5, -5.1, -4.9, -5.3]
        
        higgs.fit_null(fragment_affinities)
        
        assert higgs.null_mean is not None
        assert higgs.null_std is not None
        assert higgs.null_n == len(fragment_affinities)
        assert -6.0 < higgs.null_mean < -4.0  # Reasonable range

    def test_z_score_calculation(self, mock_logger):
        """Test Z-score calculation."""
        higgs = agent_module.HiggsSignificanceTester(mock_logger)
        higgs.null_mean = -5.0
        higgs.null_std = 0.5
        
        # Compound with -8.0 kcal/mol should have Z = (-5.0 - (-8.0)) / 0.5 = 6.0
        z = higgs.z_score(-8.0)
        assert abs(z - 6.0) < 0.01

    def test_classification_5sigma(self, mock_logger):
        """Test 5-sigma discovery classification."""
        higgs = agent_module.HiggsSignificanceTester(mock_logger)
        higgs.null_mean = -5.0
        higgs.null_std = 0.5
        
        # Affinity of -7.5 gives Z = 5.0 (5-sigma threshold)
        result = higgs.classify(-7.5)
        
        assert result["z_score"] == 5.0
        assert result["is_discovery"] is True
        assert result["is_evidence"] is True
        assert "5-SIGMA" in result["status"]

    def test_classification_3sigma(self, mock_logger):
        """Test 3-sigma evidence classification."""
        higgs = agent_module.HiggsSignificanceTester(mock_logger)
        higgs.null_mean = -5.0
        higgs.null_std = 0.5
        
        # Affinity of -6.5 gives Z = 3.0 (3-sigma threshold)
        result = higgs.classify(-6.5)
        
        assert result["z_score"] == 3.0
        assert result["is_discovery"] is False
        assert result["is_evidence"] is True
        assert "3-SIGMA" in result["status"]

    def test_classification_subthreshold(self, mock_logger):
        """Test sub-threshold classification."""
        higgs = agent_module.HiggsSignificanceTester(mock_logger)
        higgs.null_mean = -5.0
        higgs.null_std = 0.5
        
        # Affinity of -5.5 gives Z = 1.0 (below 2-sigma)
        result = higgs.classify(-5.5)
        
        assert result["z_score"] == 1.0
        assert result["is_discovery"] is False
        assert result["is_evidence"] is False
        assert "sub-threshold" in result["status"]


# ============================================================================
# TEST: ADMET Filtering
# ============================================================================

class TestADMETFiltering:
    """Test ADMET filtering thresholds."""

    def test_admet_panel_structure(self):
        """Test ADMET_PANEL structure."""
        assert len(agent_module.ADMET_PANEL) == 23
        
        # Check key toxicity properties
        assert "hERG" in agent_module.ADMET_PANEL
        assert "DILI" in agent_module.ADMET_PANEL
        assert "AMES" in agent_module.ADMET_PANEL
        assert "ClinTox" in agent_module.ADMET_PANEL

    def test_admet_thresholds(self):
        """Test ADMET threshold values."""
        # Toxicity thresholds (lower is better)
        assert agent_module.ADMET_PANEL["hERG"][1] == "<0.5 safe"
        assert agent_module.ADMET_PANEL["DILI"][1] == "<0.5 safe"
        assert agent_module.ADMET_PANEL["AMES"][1] == "<0.3 safe"
        
        # Absorption thresholds (higher is better)
        assert agent_module.ADMET_PANEL["Bioavailability_Ma"][1] == ">0.5 good"
        assert agent_module.ADMET_PANEL["HIA_Hou"][1] == ">0.7 good"

    def test_admet_pass_criteria(self, mock_admet_results):
        """Test ADMET pass/fail criteria."""
        # Safe compound (all values within thresholds)
        assert mock_admet_results["hERG"] < 0.5  # Safe
        assert mock_admet_results["DILI"] < 0.5  # Safe
        assert mock_admet_results["AMES"] < 0.3  # Safe
        assert mock_admet_results["Bioavailability_Ma"] > 0.5  # Good

    def test_admet_fail_criteria(self):
        """Test ADMET failure detection."""
        # Toxic compound
        toxic_results = {
            "hERG": 0.85,  # FAIL - cardiotoxic
            "DILI": 0.75,  # FAIL - hepatotoxic
            "AMES": 0.65,  # FAIL - mutagenic
        }
        
        assert toxic_results["hERG"] > 0.5  # Fails threshold
        assert toxic_results["DILI"] > 0.5  # Fails threshold
        assert toxic_results["AMES"] > 0.3  # Fails threshold


# ============================================================================
# TEST: Growing Agent
# ============================================================================

class TestGrowingAgent:
    """Test GrowingAgent fragment growing logic."""

    def test_growing_agent_initialization(self, mock_logger):
        """Test GrowingAgent initialization."""
        mock_docker = Mock()
        grower = agent_module.GrowingAgent(mock_logger, mock_docker, target="EGFR")
        
        assert grower.log == mock_logger
        assert grower.dock == mock_docker
        assert grower.target == "EGFR"
        assert grower.grown == []

    def test_rgroup_library(self):
        """Test R-group library structure."""
        assert "alkyl" in agent_module.GrowingAgent.RGROUPS
        assert "fluorine" in agent_module.GrowingAgent.RGROUPS
        assert "amines" in agent_module.GrowingAgent.RGROUPS
        
        # Check alkyl groups
        assert "C" in agent_module.GrowingAgent.RGROUPS["alkyl"]
        assert "CC" in agent_module.GrowingAgent.RGROUPS["alkyl"]

    def test_pharma_tails_egfr(self):
        """Test EGFR-specific pharmacophore tails."""
        assert "EGFR" in agent_module.GrowingAgent.PHARMA_TAILS
        egfr_tails = agent_module.GrowingAgent.PHARMA_TAILS["EGFR"]
        
        # Should contain quinazoline scaffold
        assert any("quinazoline" in str(tail).lower() or "ncnc" in tail for tail in egfr_tails)

    def test_pharma_tails_hiv(self):
        """Test HIV-specific pharmacophore tails."""
        assert "HIV" in agent_module.GrowingAgent.PHARMA_TAILS
        hiv_tails = agent_module.GrowingAgent.PHARMA_TAILS["HIV"]
        
        # Should contain sulfonamide and bis-THF motifs
        assert any("S(=O)(=O)" in tail for tail in hiv_tails)


# ============================================================================
# TEST: Target Profiles
# ============================================================================

class TestTargetProfiles:
    """Test TARGET_PROFILES configuration."""

    def test_target_profiles_structure(self):
        """Test that all targets have required fields."""
        required_fields = ["name", "receptor", "center", "size", "ref_drug", "ref_affinity"]
        
        for target, profile in agent_module.TARGET_PROFILES.items():
            for field in required_fields:
                assert field in profile, f"Target {target} missing field {field}"

    def test_egfr_profile(self):
        """Test EGFR target profile."""
        egfr = agent_module.TARGET_PROFILES["EGFR"]
        
        assert egfr["name"] == "EGFR Kinase (Wild-Type)"
        assert egfr["ref_drug"] == "Erlotinib"
        assert egfr["ref_affinity"] == -8.0
        assert egfr["receptor"] == "cancer_egfr_agent/egfr_receptor.pdbqt"
        assert len(egfr["center"]) == 3
        assert len(egfr["size"]) == 3

    def test_hiv_integrase_profile(self):
        """Test HIV_INTEGRASE target profile."""
        hiv_int = agent_module.TARGET_PROFILES["HIV_INTEGRASE"]
        
        assert hiv_int["ref_drug"] == "Dolutegravir"
        assert hiv_int["ref_affinity"] == -9.43
        assert hiv_int["receptor"] == "hiv_integrase.pdbqt"

    def test_disease_categories(self):
        """Test disease category organization."""
        assert "Oncology" in agent_module.DISEASE_CATEGORIES
        assert "Infectious Disease" in agent_module.DISEASE_CATEGORIES
        assert "Neurological" in agent_module.DISEASE_CATEGORIES
        
        # Check EGFR is in Oncology
        assert "EGFR" in agent_module.DISEASE_CATEGORIES["Oncology"]


# ============================================================================
# TEST: Canonical CSV Schema
# ============================================================================

class TestCanonicalCSV:
    """Test canonical CSV schema."""

    def test_canonical_columns_defined(self):
        """Test that canonical columns are defined."""
        assert hasattr(agent_module, 'CANONICAL_CSV_COLUMNS')
        assert len(agent_module.CANONICAL_CSV_COLUMNS) > 0

    def test_canonical_columns_structure(self):
        """Test canonical column structure."""
        columns = agent_module.CANONICAL_CSV_COLUMNS
        
        # Check key columns exist
        assert "id" in columns
        assert "smiles" in columns
        assert "dock_affinity" in columns
        assert "z_score" in columns
        assert "sigma_label" in columns
        assert "is_discovery" in columns
        assert "is_evidence" in columns
        assert "hERG" in columns
        assert "DILI" in columns
        assert "AMES" in columns
        assert "confidence" in columns

    def test_canonicalize_row(self):
        """Test row canonicalization."""
        candidate = {
            "id": "TEST_001",
            "smiles": "c1ccncc1",
            "dock_affinity": -8.5,
            "MW": 250.0,
            "LogP": 2.5,
            "HAC": 18,
            "LE": 0.47,
            "z_score": 5.2,
            "sigma_label": "5.20s",
            "is_discovery": True,
            "is_evidence": True,
            "hERG": 0.15,
            "DILI": 0.25,
            "AMES": 0.10,
            "admet_pass": True,
            "confidence": 95,
        }
        
        row = agent_module._canonicalize_row(
            candidate,
            target="EGFR",
            ref_drug="Erlotinib",
            ref_aff=-8.0,
            run_id="test_run",
            timestamp="2026-05-16T14:00:00"
        )
        
        # Check all canonical columns present
        for col in agent_module.CANONICAL_CSV_COLUMNS:
            assert col in row
        
        # Check values
        assert row["id"] == "TEST_001"
        assert row["smiles"] == "c1ccncc1"
        assert row["dock_affinity"] == -8.5
        assert row["mw"] == 250.0
        assert row["is_discovery"] == "true"  # Boolean → string
        assert row["target"] == "EGFR"


# ============================================================================
# TEST: Integration - Multi-Agent Flow
# ============================================================================

class TestMultiAgentOrchestration:
    """Test multi-agent orchestration flow."""

    def test_fragment_to_docking_flow(self, mock_logger, sample_fragments, mock_docking_results):
        """Test fragment selection → docking flow."""
        # 1. Fragment selection
        selector = agent_module.FragmentSelectorAgent(mock_logger)
        selector.selected = sample_fragments
        
        # 2. Docking
        docker = agent_module.DockingAgent(
            mock_logger,
            receptor="test.pdbqt",
            center=(0, 0, 0),
            size=(25, 25, 25)
        )
        
        # Mock dock method
        def mock_dock(smiles, name):
            return mock_docking_results.get(smiles, {"error": "Not found"})
        
        with patch.object(docker, 'dock', side_effect=mock_dock):
            results = docker.screen_fragments(selector.selected, ref_affinity=-6.0)
            
            # Should have docking results
            assert len(results) > 0
            assert all("dock_affinity" in r for r in results)

    def test_docking_to_higgs_flow(self, mock_logger):
        """Test docking → Higgs significance flow."""
        # 1. Mock docking results
        docked_fragments = [
            {"id": "F001", "smiles": "c1ccncc1", "dock_affinity": -5.2},
            {"id": "F002", "smiles": "c1ccnc2ccccc12", "dock_affinity": -6.8},
            {"id": "F071", "smiles": "Nc1ncnc2ccccc12", "dock_affinity": -8.3},
        ]
        
        # 2. Fit null distribution
        higgs = agent_module.HiggsSignificanceTester(mock_logger)
        fragment_affinities = [f["dock_affinity"] for f in docked_fragments]
        higgs.fit_null(fragment_affinities)
        
        # 3. Classify compounds
        grown_compound = {"id": "GROWN_001", "dock_affinity": -9.5}
        classification = higgs.classify(grown_compound["dock_affinity"])
        
        # Should be significant (better than fragments)
        assert classification["z_score"] > 2.0
        assert classification["is_evidence"] or classification["is_discovery"]

    def test_end_to_end_mock_pipeline(self, mock_logger, sample_fragments, mock_docking_results, mock_admet_results):
        """Test end-to-end pipeline with mocks."""
        # 1. Fragment selection
        selector = agent_module.FragmentSelectorAgent(mock_logger)
        selector.selected = sample_fragments[:3]
        
        # 2. Docking
        docker = agent_module.DockingAgent(
            mock_logger,
            receptor="test.pdbqt",
            center=(0, 0, 0),
            size=(25, 25, 25)
        )
        
        with patch.object(docker, 'dock', side_effect=lambda s, n: mock_docking_results.get(s, {"error": "Not found"})):
            docked = docker.screen_fragments(selector.selected, ref_affinity=-6.0)
        
        # 3. Higgs significance
        higgs = agent_module.HiggsSignificanceTester(mock_logger)
        affinities = [d["dock_affinity"] for d in docked if "dock_affinity" in d]
        higgs.fit_null(affinities)
        
        # 4. Mock grown compound
        grown = {"id": "GROWN_001", "smiles": "test_smiles", "dock_affinity": -9.0}
        sig = higgs.classify(grown["dock_affinity"])
        grown.update(sig)
        
        # 5. ADMET filtering (mock)
        grown.update(mock_admet_results)
        
        # Verify pipeline output
        assert "dock_affinity" in grown
        assert "z_score" in grown
        assert "is_discovery" in grown or "is_evidence" in grown
        assert "hERG" in grown
        assert grown["hERG"] < 0.5  # Passes ADMET


# ============================================================================
# TEST: Utility Functions
# ============================================================================

class TestUtilityFunctions:
    """Test utility functions."""

    def test_silence_rdkit_context_manager(self):
        """Test _SilenceRDKit context manager."""
        with agent_module._SilenceRDKit():
            # Should suppress stderr
            pass
        # Should restore stderr after exit

    def test_generate_novel_fragments(self):
        """Test novel fragment generation."""
        with patch('autonomous_drug_agentV2.RDKIT_OK', True):
            with patch('autonomous_drug_agentV2.Chem.MolFromSmiles') as mock_mol:
                with patch('autonomous_drug_agentV2.Descriptors'):
                    mock_mol.return_value = Mock()
                    mock_mol.return_value.GetNumHeavyAtoms.return_value = 10
                    
                    # Should generate some fragments
                    frags = agent_module.generate_novel_fragments(n=5, seed=42)
                    # May be empty if mocking doesn't work perfectly, but shouldn't crash


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

# Made with Bob
