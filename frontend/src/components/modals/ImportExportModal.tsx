import React, { useState } from 'react';
import { TuringMachine, NodeLayout, MachineExportEnvelope } from '../../types';
import { generateAutoLayout, validateMachineSemantics } from '../../utils/tape';
import { X, Copy, Download, Upload, Check, AlertCircle } from 'lucide-react';

interface ImportExportModalProps {
  machine: TuringMachine;
  layout: Record<string, NodeLayout>;
  isOpen: boolean;
  onClose: () => void;
  onImport: (machine: TuringMachine, layout: Record<string, NodeLayout>) => void;
}

export const ImportExportModal: React.FC<ImportExportModalProps> = ({
  machine,
  layout,
  isOpen,
  onClose,
  onImport,
}) => {
  const [activeTab, setActiveTab] = useState<'export' | 'import'>('export');
  const [importText, setImportText] = useState('');
  const [importError, setImportError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  if (!isOpen) return null;

  const currentEnvelope: MachineExportEnvelope = {
    schema_version: 1,
    machine,
    layout,
  };

  const exportJsonString = JSON.stringify(currentEnvelope, null, 2);

  const handleCopy = () => {
    navigator.clipboard.writeText(exportJsonString);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  const handleDownload = () => {
    const blob = new Blob([exportJsonString], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `turing_machine_${Date.now()}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const handleExecuteImport = () => {
    setImportError(null);
    if (!importText.trim()) {
      setImportError('Please paste valid JSON text into the area below.');
      return;
    }

    try {
      const parsed = JSON.parse(importText);

      // Validate schema_version
      if (parsed.schema_version !== 1) {
        setImportError(
          `Unsupported schema_version "${parsed.schema_version}". Only schema_version 1 is supported.`
        );
        return;
      }

      if (!parsed.machine || typeof parsed.machine !== 'object') {
        setImportError('Invalid JSON: missing root "machine" object.');
        return;
      }

      const importedMachine: TuringMachine = parsed.machine;
      const issues = validateMachineSemantics(importedMachine);
      const errors = issues.filter((i) => i.type === 'error');
      if (errors.length > 0) {
        setImportError(`Machine validation failed: ${errors[0].message}`);
        return;
      }

      // Validate or generate layout
      let finalLayout: Record<string, NodeLayout> = {};
      if (parsed.layout !== undefined) {
        if (!parsed.layout || typeof parsed.layout !== 'object' || Array.isArray(parsed.layout)) {
          setImportError('Layout must be an object keyed by state ID.');
          return;
        }
        const stateIds = new Set(importedMachine.states.map((s) => s.id));
        // Check for dangling layout keys
        for (const stateId of Object.keys(parsed.layout)) {
          if (!stateIds.has(stateId)) {
            setImportError(`Dangling layout entry: State "${stateId}" is not in machine states.`);
            return;
          }
          const position = parsed.layout[stateId];
          if (!position || !Number.isFinite(position.x) || !Number.isFinite(position.y)) {
            setImportError(`Layout for state "${stateId}" requires finite x and y coordinates.`);
            return;
          }
        }
        finalLayout = parsed.layout;
      } else {
        // Layout-free import: assign generated positions
        finalLayout = generateAutoLayout(
          importedMachine.states,
          importedMachine.transitions,
          importedMachine.start_state
        );
      }

      // Successfully validated: apply import and close modal
      onImport(importedMachine, finalLayout);
      onClose();
    } catch (err) {
      setImportError(`JSON Parse Error: ${err instanceof Error ? err.message : String(err)}`);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-dialog-panel" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title-group">
            <h3 className="modal-title">Machine Persistence (JSON)</h3>
            <span className="modal-schema-tag font-mono">schema_version: 1</span>
          </div>
          <button type="button" className="modal-close-btn" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        {/* Tab Selector */}
        <div className="modal-tab-row">
          <button
            type="button"
            className={`modal-tab ${activeTab === 'export' ? 'active' : ''}`}
            onClick={() => setActiveTab('export')}
          >
            Export Machine
          </button>
          <button
            type="button"
            className={`modal-tab ${activeTab === 'import' ? 'active' : ''}`}
            onClick={() => setActiveTab('import')}
          >
            Import Machine
          </button>
        </div>

        <div className="modal-body">
          {activeTab === 'export' ? (
            <div className="export-view">
              <p className="modal-instruction">
                Copy the canonical JSON definition below or download as a <code>.json</code> file. Includes state layout coordinates and deterministic transition rules.
              </p>
              <textarea
                readOnly
                value={exportJsonString}
                className="json-textarea font-mono"
                rows={12}
              />
              <div className="modal-actions-bar">
                <button type="button" className="btn btn-secondary" onClick={handleCopy}>
                  {copied ? (
                    <>
                      <Check size={14} className="text-success" />
                      <span>Copied to Clipboard!</span>
                    </>
                  ) : (
                    <>
                      <Copy size={14} />
                      <span>Copy JSON</span>
                    </>
                  )}
                </button>
                <button type="button" className="btn btn-primary" onClick={handleDownload}>
                  <Download size={14} />
                  <span>Download File (.json)</span>
                </button>
              </div>
            </div>
          ) : (
            <div className="import-view">
              <p className="modal-instruction">
                Paste a versioned JSON envelope below. The envelope must declare <code>"schema_version": 1</code>. If parsing or semantic validation fails, your current workspace will remain intact.
              </p>
              {importError && (
                <div className="modal-error-banner">
                  <AlertCircle size={15} />
                  <span>{importError}</span>
                </div>
              )}
              <textarea
                value={importText}
                onChange={(e) => setImportText(e.target.value)}
                placeholder='{\n  "schema_version": 1,\n  "machine": { ... }\n}'
                className="json-textarea font-mono"
                rows={12}
              />
              <div className="modal-actions-bar">
                <button type="button" className="btn btn-secondary" onClick={() => setImportText('')}>
                  Clear
                </button>
                <button type="button" className="btn btn-primary" onClick={handleExecuteImport}>
                  <Upload size={14} />
                  <span>Validate & Import</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

