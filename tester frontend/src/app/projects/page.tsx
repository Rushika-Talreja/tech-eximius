"use client";

import React, { useEffect, useState } from "react";
import { executeApiRequest } from "../../lib/api";
import { useConsole } from "../../lib/store";
import { ErrorDisplay } from "../../components/ErrorDisplay";
import { RawJsonViewer } from "../../components/RawJsonViewer";
import { ProjectItem } from "../../types/backend";

export default function ProjectsPage() {
  const { authMode, apiKey, addLogEntry } = useConsole();
  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<any>(null);

  // Form
  const [name, setName] = useState("DeFi Vault Core");
  const [description, setDescription] = useState("ERC-4626 vault smart contracts");

  // Selected project for inspection
  const [selectedProject, setSelectedProject] = useState<any>(null);

  const fetchProjects = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await executeApiRequest("/projects", {
        authMode,
        apiKey,
        onLog: addLogEntry,
      });
      setProjects(res.data?.items || []);
    } catch (err) {
      setError(err);
      setProjects([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProjects();
  }, [authMode]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await executeApiRequest("/projects", {
        method: "POST",
        body: { name, description },
        authMode,
        apiKey,
        onLog: addLogEntry,
      });
      fetchProjects();
    } catch (err) {
      setError(err);
    }
  };

  const handleView = async (id: string) => {
    setError(null);
    try {
      const res = await executeApiRequest(`/projects/${id}`, {
        authMode,
        apiKey,
        onLog: addLogEntry,
      });
      setSelectedProject(res.data);
    } catch (err) {
      setError(err);
    }
  };

  const handleDelete = async (id: string, projectName: string) => {
    if (!confirm(`Soft delete project "${projectName}"?`)) return;
    setError(null);
    try {
      await executeApiRequest(`/projects/${id}`, {
        method: "DELETE",
        authMode,
        apiKey,
        onLog: addLogEntry,
      });
      if (selectedProject?.id === id) {
        setSelectedProject(null);
      }
      fetchProjects();
    } catch (err) {
      setError(err);
    }
  };

  return (
    <div>
      <h2>Projects Management</h2>
      <p style={{ color: "#666", fontSize: "14px" }}>
        Exercise <code>POST /projects</code>, <code>GET /projects</code>, <code>GET /projects/&#123;id&#125;</code>, and <code>DELETE /projects/&#123;id&#125;</code>.
      </p>

      <ErrorDisplay error={error} />

      {/* Creation form */}
      <div style={{ border: "1px solid #ddd", padding: "16px", borderRadius: "4px", backgroundColor: "#fafafa", marginBottom: "20px" }}>
        <h3 style={{ margin: "0 0 12px 0" }}>Create Project</h3>
        <form onSubmit={handleCreate} style={{ display: "flex", gap: "12px", alignItems: "center" }}>
          <div>
            <label style={{ fontSize: "12px", display: "block" }}>Project Name:</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              style={{ padding: "4px 8px" }}
              required
            />
          </div>
          <div>
            <label style={{ fontSize: "12px", display: "block" }}>Description:</label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              style={{ padding: "4px 8px", width: "280px" }}
            />
          </div>
          <button
            type="submit"
            style={{
              marginTop: "16px",
              padding: "6px 14px",
              backgroundColor: "#27ae60",
              color: "#fff",
              border: "none",
              borderRadius: "4px",
              cursor: "pointer",
            }}
          >
            Create Project
          </button>
        </form>
      </div>

      {/* List */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
        <h3 style={{ margin: 0 }}>Existing Projects ({projects.length})</h3>
        <button onClick={fetchProjects} disabled={loading} style={{ padding: "4px 8px" }}>
          {loading ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
        <thead>
          <tr style={{ backgroundColor: "#f0f0f0", textAlign: "left" }}>
            <th style={{ padding: "8px", border: "1px solid #ddd" }}>Name</th>
            <th style={{ padding: "8px", border: "1px solid #ddd" }}>Description</th>
            <th style={{ padding: "8px", border: "1px solid #ddd" }}>Audits</th>
            <th style={{ padding: "8px", border: "1px solid #ddd" }}>Created At</th>
            <th style={{ padding: "8px", border: "1px solid #ddd", width: "150px" }}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {projects.length === 0 ? (
            <tr>
              <td colSpan={5} style={{ padding: "12px", textAlign: "center", color: "#888" }}>
                No projects found for active identity.
              </td>
            </tr>
          ) : (
            projects.map((p) => (
              <tr key={p.id}>
                <td style={{ padding: "6px 8px", border: "1px solid #ddd", fontWeight: "bold" }}>
                  {p.name}
                </td>
                <td style={{ padding: "6px 8px", border: "1px solid #ddd", color: "#555" }}>
                  {p.description || "-"}
                </td>
                <td style={{ padding: "6px 8px", border: "1px solid #ddd" }}>
                  {p.audit_count || 0}
                </td>
                <td style={{ padding: "6px 8px", border: "1px solid #ddd", color: "#666" }}>
                  {p.created_at}
                </td>
                <td style={{ padding: "6px 8px", border: "1px solid #ddd" }}>
                  <button
                    onClick={() => handleView(p.id)}
                    style={{ padding: "2px 8px", marginRight: "6px", cursor: "pointer" }}
                  >
                    View
                  </button>
                  <button
                    onClick={() => handleDelete(p.id, p.name)}
                    style={{
                      padding: "2px 8px",
                      backgroundColor: "#e74c3c",
                      color: "#fff",
                      border: "none",
                      borderRadius: "3px",
                      cursor: "pointer",
                    }}
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>

      {/* Selected Project Details */}
      {selectedProject && (
        <div style={{ marginTop: "20px", padding: "16px", border: "1px solid #b2bec3", borderRadius: "4px", backgroundColor: "#fdfefe" }}>
          <h3 style={{ margin: "0 0 8px 0" }}>Project Details: {selectedProject.name}</h3>
          <div style={{ fontFamily: "monospace", fontSize: "13px" }}>
            <div>ID: <strong>{selectedProject.id}</strong></div>
            <div>Org ID: <strong>{selectedProject.org_id}</strong></div>
            <div>Created By: <strong>{selectedProject.created_by}</strong></div>
            <div>Created At: <strong>{selectedProject.created_at}</strong></div>
            <div>Audit Count: <strong>{selectedProject.audit_count ?? 0}</strong></div>
          </div>
          <RawJsonViewer data={selectedProject} title="Raw Project JSON" />
        </div>
      )}

      <RawJsonViewer data={projects} title="Raw Projects List JSON" />
    </div>
  );
}

