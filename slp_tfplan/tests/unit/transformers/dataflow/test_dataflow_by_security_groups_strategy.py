from typing import List

from pytest import mark, param

from slp_tfplan.slp_tfplan.objects.tfplan_objects import TFPlanComponent, SecurityGroup
from slp_tfplan.slp_tfplan.transformers.dataflow.dataflow_by_security_groups_strategy import \
    DataflowBySecurityGroupsStrategy
from slp_tfplan.tests.util.builders import build_simple_mocked_component, build_security_group_mock, build_mocked_otm


class TestDataflowBySecurityGroupsStrategy:

    @mark.parametrize('components,security_groups', [
        param([], [], id='no components nor security groups'),
        param([], [build_security_group_mock('SG')], id='no components'),
        param([build_simple_mocked_component('A')], [], id='no sgs'),
        param([build_simple_mocked_component('A'), build_simple_mocked_component('B')],
              [build_security_group_mock('SG1'), build_security_group_mock('SG2')],
              id='unrelated_components and SGs')
    ])
    def test_no_related_components_no_dataflows(self, components: List[TFPlanComponent],
                                                security_groups: List[SecurityGroup]):
        # GIVEN a set of components and security groups

        # AND no hierarchical relationships among the components
        def are_hierarchically_related(*args, **kwargs): return False

        # AND the sgs are not related
        def are_sgs_related(*args, **kwargs): return False

        # AND the components does not belong to any SG
        def are_component_in_sg(*args, **kwargs): return False

        # WHEN DataflowBySecurityGroupsStrategy::create_dataflows is invoked
        dataflows = DataflowBySecurityGroupsStrategy().create_dataflows(
            are_hierarchically_related=are_hierarchically_related,
            are_component_in_sg=are_component_in_sg,
            are_sgs_related=are_sgs_related,
            otm=build_mocked_otm(components=components, security_groups=security_groups)
        )

        # THEN no DFs are created in the OTM
        assert not dataflows

    @mark.parametrize('related_sgs,components_in_sgs,expected_source,expected_destination,bidirectional', [
        param([('SG1', 'SG2')], {'SG1': 'A', 'SG2': 'B'}, 'A', 'B', False, id='SG1 to SG2'),
        param([('SG2', 'SG1')], {'SG1': 'A', 'SG2': 'B'}, 'B', 'A', False, id='SG2 to SG1'),
        # TODO param([('SG1', 'SG2'), ('SG2', 'SG1')], {'SG1': 'A', 'SG2': 'B'}, 'A', 'B', True, id='bidirectional')
    ])
    def test_two_related_sgs(self, related_sgs, components_in_sgs, expected_source, expected_destination,
                             bidirectional):
        # GIVEN two SGs
        sg1 = SecurityGroup(security_group_id='SG1')
        sg2 = SecurityGroup(security_group_id='SG2')

        # AND two components
        component_a = build_simple_mocked_component('A')
        component_b = build_simple_mocked_component('B')

        # AND some relationships between SGs
        # AND some relationships between SGs and components

        # AND no hierarchical relationships among the components
        def are_hierarchically_related(*args, **kwargs): return False

        # AND there are some relationships among SGs
        def are_sgs_related(sg1, sg2, **kwargs):
            return (sg1.id, sg2.id) in related_sgs

        # AND some components belong to SGs
        def are_component_in_sg(c, sg, **kwargs):
            return c.tf_resource_id in components_in_sgs.get(sg.id, [])

        # WHEN DataflowBySecurityGroupsStrategy::create_dataflows is invoked
        dataflows = DataflowBySecurityGroupsStrategy().create_dataflows(
            are_hierarchically_related=are_hierarchically_related,
            are_sgs_related=are_sgs_related,
            are_component_in_sg=are_component_in_sg,
            otm=build_mocked_otm(components=[component_a, component_b], security_groups=[sg1, sg2])
        )

        # THEN one dataflow is created
        assert len(dataflows) == 1
        dataflow = dataflows[0]

        # AND the source and destination are right
        assert dataflow.source_node == expected_source
        assert dataflow.destination_node == expected_destination
        assert dataflow.bidirectional == bidirectional