import { useState } from 'react';
import type { UnifiedHotspot } from '../services/apiClient';

export interface HotspotSidePanelProps {
  status: string;
  totalHotspots: number;
  selectedHotspot: UnifiedHotspot | null;
}

const MONTHS_MOCK = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
const MOCK_INTENSITIES = [0.1, 0.15, 0.2, 0.25, 0.4, 0.55, 0.8, 1.0, 0.85, 0.45, 0.2, 0.12];

export function HotspotSidePanel({
  status,
  totalHotspots,
  selectedHotspot,
}: HotspotSidePanelProps) {
  const [isAnalysisOpen, setIsAnalysisOpen] = useState<boolean>(true);

  return (
    <aside
      style={{
        padding: '18px',
        borderLeft: '1px solid #cbd5e1',
        background: '#f8fafc',
        overflowY: 'auto',
        display: 'flex',
        flexDirection: 'column',
        gap: '18px',
      }}
    >
      {/* Cabecera de estado */}
      <div>
        <h3 style={{ margin: '0 0 6px 0', color: '#0f172a', fontSize: '17px' }}>
          Panel de Inspección de Puntos
        </h3>
        <div style={{ fontSize: '13px', color: '#475569' }}>
          <strong>Estado:</strong> {status} ({totalHotspots} puntos en el AOI)
        </div>
      </div>

      {/* SECCIÓN A: Maqueta Visual del Selector de Fechas y Calendario (UI Mock) */}
      <section
        style={{
          background: '#ffffff',
          border: '1px solid #e2e8f0',
          borderRadius: '8px',
          padding: '14px',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
          <strong style={{ fontSize: '13px', color: '#1e293b' }}>
            Calendario y Rango de Fechas
          </strong>
          <span
            style={{
              fontSize: '11px',
              background: '#fef3c7',
              color: '#92400e',
              padding: '2px 6px',
              borderRadius: '4px',
              fontWeight: 600,
            }}
          >
            UI Mock (Sin funcionalidad)
          </span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginBottom: '12px' }}>
          <label style={{ fontSize: '12px', color: '#475569', display: 'flex', flexDirection: 'column', gap: '4px' }}>
            Desde
            <input
              type="date"
              defaultValue="2024-08-01"
              disabled
              style={{ padding: '4px 6px', border: '1px solid #cbd5e1', borderRadius: '4px', background: '#f1f5f9', color: '#64748b' }}
            />
          </label>
          <label style={{ fontSize: '12px', color: '#475569', display: 'flex', flexDirection: 'column', gap: '4px' }}>
            Hasta
            <input
              type="date"
              defaultValue="2024-08-31"
              disabled
              style={{ padding: '4px 6px', border: '1px solid #cbd5e1', borderRadius: '4px', background: '#f1f5f9', color: '#64748b' }}
            />
          </label>
        </div>

        {/* Mini matriz visual de meses (Mock) */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(12, 1fr)', gap: '3px', textAlign: 'center' }}>
          {MONTHS_MOCK.map((m, i) => (
            <div key={m} style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
              <div
                style={{
                  height: '18px',
                  borderRadius: '3px',
                  background: `rgba(239, 68, 68, ${MOCK_INTENSITIES[i]})`,
                  border: i === 7 ? '1.5px solid #991b1b' : '1px solid #e2e8f0',
                }}
                title={`${m} (Maqueta visual)`}
              />
              <span style={{ fontSize: '9px', color: '#64748b' }}>{m}</span>
            </div>
          ))}
        </div>
      </section>

      {/* SECCIÓN B: Todos los Datos Disponibles del Punto Seleccionado (10 Atributos) */}
      <section
        style={{
          background: '#ffffff',
          border: '1px solid #e2e8f0',
          borderRadius: '8px',
          padding: '14px',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
          <strong style={{ fontSize: '14px', color: '#1e293b' }}>
            Datos del Punto Seleccionado
          </strong>
          {selectedHotspot && (
            <span
              style={{
                fontSize: '11px',
                background: '#fee2e2',
                color: '#991b1b',
                padding: '2px 8px',
                borderRadius: '999px',
                fontWeight: 600,
              }}
            >
              Satélite {selectedHotspot.satellite}
            </span>
          )}
        </div>

        {!selectedHotspot ? (
          <div
            style={{
              padding: '20px 12px',
              textAlign: 'center',
              color: '#64748b',
              fontSize: '13px',
              background: '#f8fafc',
              borderRadius: '6px',
              border: '1px dashed #cbd5e1',
            }}
          >
            Haz clic en cualquier <strong>punto rojo</strong> dentro del cuadro naranja en el mapa para inspeccionar todos sus atributos.
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', fontSize: '13px' }}>
            <div style={{ gridColumn: '1 / -1', background: '#f8fafc', padding: '8px 10px', borderRadius: '6px' }}>
              <div style={{ fontSize: '11px', color: '#64748b' }}>1. Fecha y Hora UTC (datetime_utc)</div>
              <strong style={{ color: '#0f172a', fontFamily: 'monospace' }}>{selectedHotspot.datetime_utc}</strong>
            </div>

            <div style={{ background: '#f8fafc', padding: '8px 10px', borderRadius: '6px' }}>
              <div style={{ fontSize: '11px', color: '#64748b' }}>2. Satélite (satellite)</div>
              <strong style={{ color: '#0f172a' }}>{selectedHotspot.satellite}</strong>
            </div>

            <div style={{ background: '#f8fafc', padding: '8px 10px', borderRadius: '6px' }}>
              <div style={{ fontSize: '11px', color: '#64748b' }}>10. Día / Noche (day_night)</div>
              <strong style={{ color: '#0f172a' }}>
                {selectedHotspot.day_night === 'D' ? 'Diurno (D)' : selectedHotspot.day_night === 'N' ? 'Nocturno (N)' : 'N/A'}
              </strong>
            </div>

            <div style={{ background: '#f8fafc', padding: '8px 10px', borderRadius: '6px' }}>
              <div style={{ fontSize: '11px', color: '#64748b' }}>3a. Latitud (lat)</div>
              <strong style={{ color: '#0f172a', fontFamily: 'monospace' }}>{selectedHotspot.lat}°</strong>
            </div>

            <div style={{ background: '#f8fafc', padding: '8px 10px', borderRadius: '6px' }}>
              <div style={{ fontSize: '11px', color: '#64748b' }}>3b. Longitud (lon)</div>
              <strong style={{ color: '#0f172a', fontFamily: 'monospace' }}>{selectedHotspot.lon}°</strong>
            </div>

            <div style={{ background: '#f8fafc', padding: '8px 10px', borderRadius: '6px' }}>
              <div style={{ fontSize: '11px', color: '#64748b' }}>4. Temperatura 1 / Brillo (temp_1)</div>
              <strong style={{ color: '#0f172a' }}>
                {selectedHotspot.temp_1 !== null ? `${selectedHotspot.temp_1} K` : 'N/A'}
              </strong>
            </div>

            <div style={{ background: '#f8fafc', padding: '8px 10px', borderRadius: '6px' }}>
              <div style={{ fontSize: '11px', color: '#64748b' }}>5. Temperatura 2 (temp_2)</div>
              <strong style={{ color: '#0f172a' }}>
                {selectedHotspot.temp_2 !== null ? `${selectedHotspot.temp_2} K` : 'N/A'}
              </strong>
            </div>

            <div style={{ background: '#f8fafc', padding: '8px 10px', borderRadius: '6px' }}>
              <div style={{ fontSize: '11px', color: '#64748b' }}>6. Geometría Píxel (pixel_geom)</div>
              <strong style={{ color: '#0f172a' }}>
                {selectedHotspot.pixel_geom !== null ? `${selectedHotspot.pixel_geom} km²` : 'N/A'}
              </strong>
            </div>

            <div style={{ background: '#f8fafc', padding: '8px 10px', borderRadius: '6px' }}>
              <div style={{ fontSize: '11px', color: '#64748b' }}>7. Potencia Radiativa (frp)</div>
              <strong style={{ color: '#dc2626' }}>{selectedHotspot.frp} MW</strong>
            </div>

            <div style={{ background: '#f8fafc', padding: '8px 10px', borderRadius: '6px' }}>
              <div style={{ fontSize: '11px', color: '#64748b' }}>8. Confianza (confidence)</div>
              <strong style={{ color: '#0f172a', textTransform: 'capitalize' }}>{selectedHotspot.confidence}</strong>
            </div>

            <div style={{ background: '#f8fafc', padding: '8px 10px', borderRadius: '6px' }}>
              <div style={{ fontSize: '11px', color: '#64748b' }}>9. Tipo de Anomalía (fire_type)</div>
              <strong style={{ color: '#0f172a' }}>
                {selectedHotspot.fire_type !== null ? `Tipo ${selectedHotspot.fire_type}` : 'N/A'}
              </strong>
            </div>
          </div>
        )}
      </section>

      {/* SECCIÓN C: Desplegable para Datos Procesados del Otro Equipo (WIP / No definidos aún) */}
      <section
        style={{
          background: '#ffffff',
          border: '1px solid #cbd5e1',
          borderRadius: '8px',
          overflow: 'hidden',
        }}
      >
        <button
          type="button"
          onClick={() => setIsAnalysisOpen((prev) => !prev)}
          style={{
            width: '100%',
            padding: '12px 14px',
            background: '#f1f5f9',
            border: 'none',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            cursor: 'pointer',
            textAlign: 'left',
          }}
        >
          <div>
            <strong style={{ fontSize: '13px', color: '#0f172a', display: 'block' }}>
              Análisis Procesado del Punto (Equipo de Datos)
            </strong>
            <span style={{ fontSize: '11px', color: '#64748b' }}>
              Métricas avanzadas y armonización en desarrollo (WIP)
            </span>
          </div>
          <span style={{ fontSize: '14px', color: '#475569', fontWeight: 700 }}>
            {isAnalysisOpen ? '▼' : '▶'}
          </span>
        </button>

        {isAnalysisOpen && (
          <div style={{ padding: '14px', borderTop: '1px solid #e2e8f0', fontSize: '12px', color: '#475569' }}>
            <p style={{ margin: '0 0 10px 0', lineHeight: 1.4 }}>
              Espacio reservado para los indicadores estadísticos y de calibración que el equipo de análisis entregará sobre el punto seleccionado:
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {[
                { label: 'Factor de Armonización Sensor (MODIS/VIIRS)', value: 'Pendiente de definición (WIP)' },
                { label: 'Percentil Histórico en Celda Espacial', value: 'Pendiente de definición (WIP)' },
                { label: 'Índice de Anomalía Estacional Local', value: 'Pendiente de definición (WIP)' },
                { label: 'Recurrencia / Persistencia del Foco', value: 'Pendiente de definición (WIP)' },
              ].map((item) => (
                <div
                  key={item.label}
                  style={{
                    padding: '8px 10px',
                    background: '#f8fafc',
                    border: '1px dashed #cbd5e1',
                    borderRadius: '6px',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    gap: '8px',
                  }}
                >
                  <span style={{ color: '#334155', fontWeight: 500 }}>{item.label}</span>
                  <span
                    style={{
                      fontSize: '11px',
                      color: '#64748b',
                      fontStyle: 'italic',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {selectedHotspot ? item.value : 'Sin punto seleccionado'}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </section>
    </aside>
  );
}
