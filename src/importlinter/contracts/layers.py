from importlinter.domain.contract import Contract, ContractCheck
from importlinter.domain.imports import Module
from importlinter.domain import fields
from importlinter.domain.ports.graph import ImportGraph
from importlinter.domain import helpers
from importlinter.application import output


class LayersContract(Contract):
    type_name = 'layers'

    containers = fields.ListField(subfield=fields.StringField())
    layers = fields.ListField(subfield=fields.StringField())
    ignore_imports = fields.ListField(subfield=fields.DirectImportField(), required=False)

    def check(self, graph: ImportGraph) -> ContractCheck:
        is_kept = True
        invalid_chains = []

        direct_imports_to_ignore = self.ignore_imports if self.ignore_imports else []
        removed_imports = helpers.pop_imports(graph, direct_imports_to_ignore)  # type: ignore

        for index, higher_layer in enumerate(self.layers):  # type: ignore
            for lower_layer in self.layers[index + 1:]:  # type: ignore
                for container in self.containers:  # type: ignore
                    higher_layer_package = Module('.'.join([container, higher_layer]))
                    lower_layer_package = Module('.'.join([container, lower_layer]))

                    descendants = set(
                        map(Module, graph.find_descendants(higher_layer_package.name)))
                    higher_layer_modules = {higher_layer_package} | descendants

                    descendants = set(map(Module, graph.find_descendants(lower_layer_package.name)))
                    lower_layer_modules = {lower_layer_package} | descendants

                    layer_chain_data = {
                        'higher_layer': higher_layer_package.name,
                        'lower_layer': lower_layer_package.name,
                        'chains': [],
                    }
                    assert isinstance(layer_chain_data['chains'], list)  # For type checker.
                    for higher_layer_module in higher_layer_modules:
                        for lower_layer_module in lower_layer_modules:
                            chain = graph.find_shortest_chain(
                                importer=lower_layer_module.name,
                                imported=higher_layer_module.name,
                            )
                            if chain:
                                is_kept = False
                                chain_data = []
                                for importer, imported in [
                                    (chain[i], chain[i + 1]) for i in range(len(chain) - 1)
                                ]:
                                    import_details = graph.get_import_details(importer=importer,
                                                                              imported=imported)
                                    line_numbers = tuple(j['line_number'] for j in import_details)
                                    chain_data.append(
                                        {
                                            'importer': importer,
                                            'imported': imported,
                                            'line_numbers': line_numbers,
                                        },
                                    )

                                layer_chain_data['chains'].append(chain_data)
                    if layer_chain_data['chains']:
                        invalid_chains.append(layer_chain_data)

        helpers.add_imports(graph, removed_imports)

        return ContractCheck(kept=is_kept, metadata={'invalid_chains': invalid_chains})

    def render_broken_contract(self, check: ContractCheck) -> None:
        for chains_data in check.metadata['invalid_chains']:
            higher_layer, lower_layer = chains_data['higher_layer'], chains_data['lower_layer']
            output.print(f"{lower_layer} is not allowed to import {higher_layer}:")
            output.new_line()

            for chain in chains_data['chains']:
                first_line = True
                for direct_import in chain:
                    importer, imported = direct_import['importer'], direct_import['imported']
                    line_numbers = ', '.join(f'l.{n}' for n in direct_import['line_numbers'])
                    import_string = f"{importer} -> {imported} ({line_numbers})"
                    if first_line:
                        output.print(f"-   {import_string}")
                        first_line = False
                    else:
                        output.indent_cursor()
                        output.print(import_string)
                output.new_line()

            output.new_line()