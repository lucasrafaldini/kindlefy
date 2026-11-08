#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::net::TcpStream;
use std::path::{Path, PathBuf};
use std::process::{Child, Command};
use std::sync::Mutex;
use std::time::Duration;
use tauri::{Emitter, Manager};

pub struct SidecarState(pub Mutex<Option<Child>>);

fn is_port_open(port: u16) -> bool {
    TcpStream::connect_timeout(
        &std::net::SocketAddr::from(([127, 0, 0, 1], port)),
        Duration::from_millis(300),
    )
    .is_ok()
}

fn find_uv_executable() -> Option<PathBuf> {
    let candidate_paths = [
        PathBuf::from("/Users/outis/.local/bin/uv"),
        PathBuf::from("/opt/homebrew/bin/uv"),
        PathBuf::from("/usr/local/bin/uv"),
    ];
    for p in candidate_paths {
        if p.exists() {
            return Some(p);
        }
    }
    // Fallback to searching PATH via `which uv`
    if let Ok(out) = Command::new("which").arg("uv").output() {
        if out.status.success() {
            let s = String::from_utf8_lossy(&out.stdout).trim().to_string();
            if !s.is_empty() {
                return Some(PathBuf::from(s));
            }
        }
    }
    None
}

fn kill_stale_engine() {
    #[cfg(unix)]
    {
        let _ = Command::new("pkill").args(["-9", "-f", "kindlefy-engine"]).output();
        std::thread::sleep(Duration::from_millis(250));
    }
}

fn spawn_python_engine() -> Option<Child> {
    if is_port_open(8765) {
        println!("Kindlefy sidecar engine já está ativo na porta 8765.");
        return None;
    }

    let engine_dir = Path::new("/Volumes/VAULT/Code/kindlefy/engine");
    let venv_bin = Path::new("/Volumes/VAULT/Code/kindlefy/engine/.venv/bin/kindlefy-engine");

    let mut cmd = if venv_bin.exists() {
        let mut c = Command::new(venv_bin);
        c.args(["serve", "--host", "127.0.0.1", "--port", "8765"]);
        c
    } else if let Some(uv_path) = find_uv_executable() {
        let mut c = Command::new(uv_path);
        c.args([
            "run",
            "kindlefy-engine",
            "serve",
            "--host",
            "127.0.0.1",
            "--port",
            "8765",
        ]);
        c
    } else {
        eprintln!("Aviso: nem .venv/bin/kindlefy-engine nem `uv` encontrados para iniciar o sidecar.");
        return None;
    };

    if engine_dir.exists() {
        cmd.current_dir(engine_dir);
    }
    cmd.env("PYTHONUNBUFFERED", "1");
    cmd.env("PATH", "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin");

    // Direct logs to ~/Library/Logs/Kindlefy/engine.log for troubleshooting
    if let Ok(home) = std::env::var("HOME") {
        let log_dir = PathBuf::from(home).join("Library/Logs/Kindlefy");
        let _ = std::fs::create_dir_all(&log_dir);
        let log_file_path = log_dir.join("engine.log");
        if let Ok(log_file) = std::fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(log_file_path)
        {
            if let Ok(err_file) = log_file.try_clone() {
                cmd.stdout(log_file);
                cmd.stderr(err_file);
            }
        }
    }

    let child = cmd.spawn().ok();
    println!("[Kindlefy Engine] Processo backend iniciado com sucesso.");
    child
}

#[tauri::command]
fn restart_engine(state: tauri::State<SidecarState>) -> Result<bool, String> {
    kill_stale_engine();
    if let Ok(mut guard) = state.0.lock() {
        if let Some(mut old_child) = guard.take() {
            let _ = old_child.kill();
        }
        let new_child = spawn_python_engine();
        *guard = new_child;
        Ok(true)
    } else {
        Err("Falha ao obter lock do estado do sidecar".to_string())
    }
}

#[tauri::command]
fn open_file_dialog() -> Option<String> {
    let script = r#"try
        POSIX path of (choose file of type {"pdf", "txt", "md", "docx", "epub", "png", "jpg", "jpeg", "webp", "tiff"} with prompt "Selecione o livro ou PDF para formatar no Kindlefy:")
    on error
        return ""
    end try"#;
    let output = Command::new("osascript")
        .arg("-e")
        .arg(script)
        .output()
        .ok()?;

    if output.status.success() {
        let path = String::from_utf8_lossy(&output.stdout).trim().to_string();
        if !path.is_empty() {
            return Some(path);
        }
    }
    None
}

fn main() {
    kill_stale_engine();
    tauri::Builder::default()
        .setup(|app| {
            let child = spawn_python_engine();
            app.manage(SidecarState(Mutex::new(child)));

            // Watchdog: monitora a saúde do backend na porta 8765 e o reinicia se cair
            let app_handle = app.handle().clone();
            std::thread::spawn(move || {
                let mut last_spawn = std::time::Instant::now();
                loop {
                    std::thread::sleep(Duration::from_secs(4));
                    if !is_port_open(8765) {
                        if last_spawn.elapsed() >= Duration::from_secs(12) {
                            last_spawn = std::time::Instant::now();
                            println!("[Watchdog] Motor editorial offline na porta 8765. Reiniciando...");
                            if let Some(state) = app_handle.try_state::<SidecarState>() {
                                if let Ok(mut guard) = state.0.lock() {
                                    if !is_port_open(8765) {
                                        if let Some(mut old_child) = guard.take() {
                                            let _ = old_child.kill();
                                        }
                                        let new_child = spawn_python_engine();
                                        *guard = new_child;
                                    }
                                }
                            } else {
                                let _ = spawn_python_engine();
                            }
                        }
                    }
                }
            });

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![restart_engine, open_file_dialog])
        .on_window_event(|window, event| {
            match event {
                tauri::WindowEvent::DragDrop(drop_event) => match drop_event {
                    tauri::DragDropEvent::Enter { .. } | tauri::DragDropEvent::Over { .. } => {
                        let _ = window.emit("kindlefy-drag-hover", true);
                    }
                    tauri::DragDropEvent::Drop { paths, .. } => {
                        let _ = window.emit("kindlefy-drag-hover", false);
                        if let Some(first_path) = paths.first() {
                            let p = first_path.to_string_lossy().to_string();
                            let _ = window.emit("kindlefy-file-dropped", p);
                        }
                    }
                    tauri::DragDropEvent::Leave => {
                        let _ = window.emit("kindlefy-drag-hover", false);
                    }
                    _ => {}
                },
                tauri::WindowEvent::Destroyed => {
                    if let Some(state) = window.try_state::<SidecarState>() {
                        if let Ok(mut guard) = state.0.lock() {
                            if let Some(mut child) = guard.take() {
                                let _ = child.kill();
                            }
                        }
                    }
                }
                _ => {}
            }
        })
        .build(tauri::generate_context!())
        .expect("Erro ao construir aplicação Tauri Kindlefy")
        .run(|app_handle, event| {
            if let tauri::RunEvent::ExitRequested { .. } = event {
                if let Some(state) = app_handle.try_state::<SidecarState>() {
                    if let Ok(mut guard) = state.0.lock() {
                        if let Some(mut child) = guard.take() {
                            let _ = child.kill();
                        }
                    }
                }
            } else if let tauri::RunEvent::Opened { urls } = event {
                for url in urls {
                    if let Ok(path) = url.to_file_path() {
                        let p = path.to_string_lossy().to_string();
                        let _ = app_handle.emit("kindlefy-file-dropped", p);
                    }
                }
            }
        });
}
