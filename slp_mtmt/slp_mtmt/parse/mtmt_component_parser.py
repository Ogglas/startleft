from otm.otm.otm import Component
from slp_mtmt.slp_mtmt.entity.mtmt_entity_border import MTMBorder
from slp_mtmt.slp_mtmt.mtmt_entity import MTMT
from slp_mtmt.slp_mtmt.mtmt_mapping_file_loader import MTMTMapping
from slp_mtmt.slp_mtmt.parse.mtmt_trustzone_parser import MTMTTrustzoneParser
from slp_mtmt.slp_mtmt.parse.resolvers.resolvers import get_type_resolver
from slp_mtmt.slp_mtmt.util.border_parent_calculator import BorderParentCalculator


class MTMTComponentParser:

    def __init__(self, source: MTMT, mapping: MTMTMapping, trustzone_parser: MTMTTrustzoneParser):
        self.source = source
        self.mapping = mapping
        self.trustzoneParser = trustzone_parser

    def parse(self):
        components = []
        for mtmt_border in self.source.borders:
            if mtmt_border.is_component:
                mtmt_type = self.__calculate_otm_type(mtmt_border)
                if mtmt_type is not None:
                    components.append(self.__create_component(mtmt_border))
        return components

    def __create_component(self, border: MTMBorder) -> Component:
        trustzone_id = self.__get_trustzone_id(border)
        mtmt_type = self.__calculate_otm_type(border)
        if mtmt_type is not None:
            return Component(id=border.id,
                             name=border.name,
                             type=mtmt_type,
                             parent_type="trustZone",
                             parent=trustzone_id,
                             properties=border.properties)

    def __calculate_otm_type(self, border: MTMBorder) -> str:
        return self.__get_label_value(border)

    def __get_label_value(self, border: MTMBorder):
        label = border.stencil_name
        if label not in self.mapping.mapping_components:
            return None
        map_ = self.mapping.mapping_components[label]

        return get_type_resolver(label).resolve(map_, border)

    def __get_trustzone_id(self, border: MTMBorder):
        parent_calculator = BorderParentCalculator()
        for candidate in self.source.borders:
            if parent_calculator.is_parent(candidate, border):
                return self.trustzoneParser.calculate_otm_id(candidate)
        return ""
