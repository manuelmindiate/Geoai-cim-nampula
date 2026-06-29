def classificar_risco_zona(indice_final, total_reportes, prioridade_alta):
    risco = indice_final

    risco += total_reportes * 2
    risco += prioridade_alta * 5

    if risco > 100:
        risco = 100

    if risco >= 85:
        return risco, "Crítico", "Zona sob pressão extrema"
    elif risco >= 70:
        return risco, "Alto", "Zona em alerta urbano"
    elif risco >= 50:
        return risco, "Médio", "Zona em monitorização"
    else:
        return risco, "Baixo", "Zona estável"