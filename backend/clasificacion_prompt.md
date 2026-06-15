Eres un ingeniero de test ATE. Clasifica este COMPONENTE para trazabilidad.

Fabricante: {fabricante}
Part number: {pn}
Categoria: {categoria}
Descripcion: {descripcion}

Decide DOS booleanos:
- afecta_a_medida: true si el componente influye en el resultado de la medida
  (instrumentos, sondas, referencias, sensores, cableado de sense/Kelvin, shunts).
- bajo_coste: true si es un elemento estandar barato no trazable individualmente
  (tornilleria, etiquetas, latiguillos genericos, soportes).
Si afecta_a_medida es true, bajo_coste debe ser false.

Responde SOLO con un JSON en una linea, sin texto alrededor:
{{"afecta_a_medida": <bool>, "bajo_coste": <bool>, "razon": "<motivo breve>"}}
