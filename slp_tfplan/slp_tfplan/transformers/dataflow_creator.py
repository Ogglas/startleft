import uuid
from typing import Dict, List

from networkx import DiGraph

from otm.otm.entity.parent_type import ParentType
from otm.otm.entity.dataflow import Dataflow
from slp_tfplan.slp_tfplan.graph.relationships_extractor import RelationshipsExtractor
from slp_tfplan.slp_tfplan.objects.tfplan_objects import TFPlanOTM, TFPlanComponent, SecurityGroup
from slp_tfplan.slp_tfplan.transformers.transformer import Transformer


def find_component_by_id(component_id: str, components: List[TFPlanComponent]):
    return next(filter(lambda c: c.id == component_id, components))


def create_dataflow(source_component: TFPlanComponent, target_component: TFPlanComponent, bidirectional: bool = False):
    return Dataflow(
        # FIXME Generate deterministic ID
        dataflow_id=str(uuid.uuid4()),
        name=f'{source_component.name} to {target_component.name}',
        source_node=source_component.id,
        destination_node=target_component.id,
        bidirectional=bidirectional
    )


class DataflowCreator(Transformer):

    def __init__(self, otm: TFPlanOTM, graph: DiGraph):
        super().__init__(otm, graph)

        self.components: [TFPlanComponent] = otm.components
        self.security_groups: [SecurityGroup] = otm.security_groups
        self.dataflows: [Dataflow] = otm.dataflows

        self.relationships_extractor = RelationshipsExtractor(
            mapped_resources_ids=self.otm.mapped_resources_ids,
            graph=self.graph
        )

    def transform(self):
        self.dataflows.extend(self.__create_dataflows_from_straight_relationships())
        self.dataflows.extend(self.__create_dataflows_from_sgs())

    def __create_dataflows_from_straight_relationships(self):
        dataflows = []

        for component in self.components:
            for related_component in self.components:
                if component == related_component or self.__are_hierarchically_related(component, related_component):
                    continue

                if self.relationships_extractor.exist_valid_path(component.tf_resource_id,
                                                                 related_component.tf_resource_id):
                    dataflows.append(create_dataflow(component, related_component))

        return dataflows

    def __create_dataflows_from_sgs(self):
        dataflows = []

        components_in_sgs = self.__match_components_and_sgs()
        if not components_in_sgs:
            return dataflows

        for source_sg, target_sgs in self.__find_sgs_relationships().items():
            if source_sg not in components_in_sgs:
                continue

            for target_sg in target_sgs:
                if target_sg in components_in_sgs:
                    dataflows.extend(self.__create_dataflows_among_components(
                        components_in_sgs[source_sg], components_in_sgs[target_sg]))

        return dataflows

    def __match_components_and_sgs(self) -> Dict[str, List[TFPlanComponent]]:
        components_in_sgs: Dict[str, List[TFPlanComponent]] = {}

        for security_group in self.security_groups:
            components_in_sg = []
            for component in self.components:
                if self.__are_components_related_by_graph(component, security_group) or \
                        self.__are_related_by_launch_template(component, security_group):
                    components_in_sg.append(component)

            if components_in_sg:
                components_in_sgs[security_group.id] = components_in_sg

        return components_in_sgs

    def __are_components_related_by_graph(self, component: TFPlanComponent,
                                          security_group: SecurityGroup) -> bool:
        return self.relationships_extractor.exist_valid_path(component.tf_resource_id, security_group.id) or \
            self.relationships_extractor.exist_valid_path(security_group.id, component.tf_resource_id)

    def __are_related_by_launch_template(self, component: TFPlanComponent, security_group: SecurityGroup) -> bool:
        for launch_template in self.otm.launch_templates:
            if not self.relationships_extractor.exist_valid_path(component.tf_resource_id, launch_template.id):
                continue
            if security_group.id in launch_template.security_groups_ids:
                return True

    def __find_sgs_relationships(self) -> Dict[str, List[str]]:
        sgs_relationships: Dict[str, List[str]] = {}

        for source_sg in self.security_groups:
            sg_relationships = []

            for target_sg in self.security_groups:
                if source_sg.id == target_sg.id:
                    continue

                if self.__are_sgs_related_by_configuration(source_sg, target_sg) or \
                        self.__are_sgs_related_by_graph(source_sg, target_sg):
                    sg_relationships.append(target_sg.id)

            if sg_relationships:
                sgs_relationships[source_sg.id] = list(set(sg_relationships))

        return sgs_relationships

    def __are_sgs_related_by_configuration(self, source_sg: SecurityGroup,
                                           target_sg: SecurityGroup) -> bool:
        return source_sg.id in target_sg.ingress_sgs or target_sg.id in source_sg.egress_sgs

    def __are_sgs_related_by_graph(self, source_sg: SecurityGroup, target_sg: SecurityGroup) -> bool:
        return self.relationships_extractor.exist_valid_path(target_sg.id, source_sg.id)

    def __create_dataflows_among_components(self,
                                            source_components: List[TFPlanComponent],
                                            target_components: List[TFPlanComponent]):
        dataflows = []

        for source_component in source_components:
            for target_component in target_components:
                if not self.__are_hierarchically_related(source_component, target_component):
                    dataflows.append(create_dataflow(source_component, target_component))

        return dataflows

    def __are_hierarchically_related(self, first: TFPlanComponent, second: TFPlanComponent) -> bool:
        return first.id == second.id or \
                self.__is_ancestor(first, second) or self.__is_ancestor_of_any_clon(first, second)\
                or self.__is_ancestor(second, first) or self.__is_ancestor_of_any_clon(second, first)

    def __is_ancestor(self, component: TFPlanComponent, ancestor: TFPlanComponent) -> bool:
        return component.parent_type == ParentType.COMPONENT and \
            (component.parent == ancestor.id
             or self.__is_ancestor(find_component_by_id(component.parent, self.components), ancestor))

    def __is_ancestor_of_any_clon(self, component: TFPlanComponent, ancestor: TFPlanComponent) -> bool:
        if not component.clones_ids:
            return False

        for clon_id in component.clones_ids:
            if self.__is_ancestor(find_component_by_id(clon_id, self.components), ancestor):
                return True

        return False


