#!/usr/bin/env python3
"""
interface.py — RoMan Interface Node
====================================
Nó ROS2 (Jazzy) com interface gráfica PyQt5.

Fase 1 — Formulário:
  Exibe campos: ID, Name, Gender + botão Submit.
  Ao submeter: publica o ID em /id (std_msgs/String).

Fase 2 — Painel de Experimento:
  Exibe o ID no topo.
  8 caixas divididas em:
    - Justification (4 caixas, esquerda)
    - No Justification (4 caixas, direita)
  Recebe dados de /exp_data (roman_msgs/ExpData) e preenche as caixas.
  Botão "Send Command" envia /sam_data (roman_msgs/SamData) com a caixa selecionada.
  Após envio: caixa vira vermelho e fica bloqueada.
"""

import sys
import threading

import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Int32

# Tenta importar as mensagens customizadas
try:
    from roman_msgs.msg import ExpData, SamData, CandidateData
    CUSTOM_MSGS = True
except ImportError:
    CUSTOM_MSGS = False
    print('[WARN] roman_msgs não encontrado. Usando fallback com std_msgs.')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QMainWindow, QStackedWidget,
    QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QComboBox,
    QFrame, QSizePolicy, QScrollArea
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QFont, QColor, QPalette, QLinearGradient, QPainter, QBrush


# ─────────────────────────────────────────────────────────────────────────────
# Constantes de estilo
# ─────────────────────────────────────────────────────────────────────────────

DARK_BG      = "#0D0F14"
PANEL_BG     = "#13161D"
CARD_DEFAULT = "#1C3A2E"   # verde escuro (disponível)
CARD_SELECTED = "#2ECC71"  # verde vivo (selecionado)
CARD_SENT    = "#4A1010"   # vermelho escuro (enviado)
ACCENT_GREEN = "#2ECC71"
ACCENT_RED   = "#E74C3C"
TEXT_PRIMARY = "#E8EDF5"
TEXT_MUTED   = "#6B7A99"
BORDER_COLOR = "#252B3A"
ACCENT_YELLOW = "#F1C40F"   # ── ADICIONAR: cor do botão Trigger
ACCENT_BLUE   = "#2E86C1"   # ── ADICIONAR: cor do card Recycle
ACCENT_ORANGE = "#E67E22"   # ── ADICIONAR: cor do card Waste

STYLE_MAIN = f"""
QMainWindow, QWidget {{
    background-color: {DARK_BG};
    color: {TEXT_PRIMARY};
    font-family: 'Courier New', monospace;
}}
QLabel {{
    color: {TEXT_PRIMARY};
    background: transparent;
}}
QLineEdit {{
    background-color: {PANEL_BG};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_COLOR};
    border-radius: 6px;
    padding: 10px 14px;
    font-size: 14px;
    font-family: 'Courier New', monospace;
}}
QLineEdit:focus {{
    border: 1px solid {ACCENT_GREEN};
}}
QComboBox {{
    background-color: {PANEL_BG};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_COLOR};
    border-radius: 6px;
    padding: 10px 14px;
    font-size: 14px;
    font-family: 'Courier New', monospace;
}}
QComboBox::drop-down {{ border: none; width: 30px; }}
QComboBox QAbstractItemView {{
    background-color: {PANEL_BG};
    color: {TEXT_PRIMARY};
    selection-background-color: {ACCENT_GREEN};
    selection-color: {DARK_BG};
}}
QPushButton#submitBtn {{
    background-color: {ACCENT_GREEN};
    color: {DARK_BG};
    border: none;
    border-radius: 8px;
    padding: 12px 32px;
    font-size: 14px;
    font-weight: bold;
    font-family: 'Courier New', monospace;
    letter-spacing: 2px;
}}
QPushButton#submitBtn:hover  {{ background-color: #27ae60; }}
QPushButton#submitBtn:pressed {{ background-color: #1e8449; }}
QPushButton#sendBtn {{
    background-color: transparent;
    color: {ACCENT_GREEN};
    border: 2px solid {ACCENT_GREEN};
    border-radius: 8px;
    padding: 10px 28px;
    font-size: 13px;
    font-weight: bold;
    font-family: 'Courier New', monospace;
    letter-spacing: 2px;
}}
QPushButton#sendBtn:hover    {{ background-color: {ACCENT_GREEN}; color: {DARK_BG}; }}
QPushButton#sendBtn:pressed  {{ background-color: #27ae60; color: {DARK_BG}; }}
QPushButton#sendBtn:disabled {{ color: {TEXT_MUTED}; border-color: {TEXT_MUTED}; }}
QPushButton#triggerBtn {{
    background-color: {ACCENT_YELLOW};
    color: {DARK_BG};
    border: none;
    border-radius: 8px;
    padding: 12px 32px;
    font-size: 14px;
    font-weight: bold;
    font-family: 'Courier New', monospace;
    letter-spacing: 2px;
}}
QPushButton#triggerBtn:hover   {{ background-color: #d4ac0d; }}
QPushButton#triggerBtn:pressed {{ background-color: #b7950b; }}
QPushButton#resultSendBtn {{
    background-color: transparent;
    color: {ACCENT_GREEN};
    border: 2px solid {ACCENT_GREEN};
    border-radius: 8px;
    padding: 10px 28px;
    font-size: 13px;
    font-weight: bold;
    font-family: 'Courier New', monospace;
    letter-spacing: 2px;
}}
QPushButton#resultSendBtn:hover    {{ background-color: {ACCENT_GREEN}; color: {DARK_BG}; }}
QPushButton#resultSendBtn:pressed  {{ background-color: #27ae60; color: {DARK_BG}; }}
QPushButton#resultSendBtn:disabled {{ color: {TEXT_MUTED}; border-color: {TEXT_MUTED}; }}
QScrollArea {{ border: none; background: transparent; }}
"""

# ─────────────────────────────────────────────────────────────────────────────
# Widget: Caixa de item do experimento
# ─────────────────────────────────────────────────────────────────────────────

class ItemCard(QFrame):
    """Caixa clicável que representa um item do experimento."""

    clicked = pyqtSignal(int)  # emite o índice da caixa

    def __init__(self, index: int, parent=None):
        super().__init__(parent)
        self.index = index
        self.is_sent = False
        self.is_selected = False
        self.data = {}

        self.setFixedSize(210, 140)
        self.setCursor(Qt.PointingHandCursor)
        self._apply_style("default")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(5)

        self.lbl_item = QLabel("—")
        self.lbl_item.setFont(QFont("Courier New", 12, QFont.Bold))
        self.lbl_item.setAlignment(Qt.AlignCenter)
        self.lbl_item.setWordWrap(True)

        self.lbl_diff = QLabel("")
        self.lbl_diff.setFont(QFont("Courier New", 10))
        self.lbl_diff.setAlignment(Qt.AlignCenter)
        self.lbl_diff.setStyleSheet(f"color: {TEXT_MUTED};")

        self.lbl_gt = QLabel("")
        self.lbl_gt.setFont(QFont("Courier New", 10))
        self.lbl_gt.setAlignment(Qt.AlignCenter)
        self.lbl_gt.setStyleSheet(f"color: {TEXT_MUTED};")

        layout.addStretch()
        layout.addWidget(self.lbl_item)
        layout.addWidget(self.lbl_diff)
        layout.addWidget(self.lbl_gt)
        layout.addStretch()

    def _apply_style(self, state: str):
        if state == "default":
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {CARD_DEFAULT};
                    border: 2px solid #1e5c40;
                    border-radius: 10px;
                }}
            """)
        elif state == "selected":
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: #1a4d30;
                    border: 2px solid {ACCENT_GREEN};
                    border-radius: 10px;
                }}
            """)
        elif state == "sent":
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {CARD_SENT};
                    border: 2px solid #7B241C;
                    border-radius: 10px;
                }}
            """)

    def populate(self, item_name: str, difficulty: str, ground_truth: str,
                classification: str = '', suggestion: bool = False):
        self.data = {
            "item_name": item_name,
            "difficulty": difficulty,
            "ground_truth": ground_truth,
            "classification": classification,
            "suggestion": suggestion,
        }
        self.lbl_item.setText(item_name)
        self.lbl_diff.setText(f"Dif: {difficulty}")
        self.lbl_gt.setText(f"GT: {ground_truth}")
        self.lbl_diff.setStyleSheet(f"color: {TEXT_MUTED};")
        self.lbl_gt.setStyleSheet(f"color: {TEXT_MUTED};")

    def set_selected(self, selected: bool):
        if self.is_sent:
            return
        self.is_selected = selected
        self._apply_style("selected" if selected else "default")

    def mark_sent(self):
        """Marca a caixa como enviada (vermelho, bloqueada)."""
        self.is_sent = True
        self.is_selected = False
        self._apply_style("sent")
        self.lbl_diff.setStyleSheet(f"color: #a93226;")
        self.lbl_gt.setStyleSheet(f"color: #a93226;")
        self.setCursor(Qt.ForbiddenCursor)

    def mousePressEvent(self, event):
        if not self.is_sent and self.data:
            self.clicked.emit(self.index)



# ─────────────────────────────────────────────────────────────────────────────
# ── ADICIONAR: Widget de card selecionável para ResultScreen
# ─────────────────────────────────────────────────────────────────────────────



class ResultOptionCard(QFrame):
    """
    Card clicável de escolha binária na ResultScreen.
    value: 'recycle' ou 'waste'
    """

    from PyQt5.QtCore import pyqtSignal
    clicked = pyqtSignal(str)   # emite o value do card

    # Cores por tipo
    COLORS = {
        "recycle": {
            "default_bg":  "#0D2137",
            "default_bd":  "#1A4A6E",
            "selected_bg": "#1A3A5C",
            "selected_bd": ACCENT_BLUE if False else "#2E86C1",
            "label":       "#2E86C1",
        },
        "waste": {
            "default_bg":  "#2D1A0A",
            "default_bd":  "#7D4010",
            "selected_bg": "#4A2A0D",
            "selected_bd": "#E67E22",
            "label":       "#E67E22",
        },
    }

    def __init__(self, value: str, label: str, parent=None):
        super().__init__(parent)
        self.value = value          # 'recycle' | 'waste'
        self.is_selected = False
        c = self.COLORS[value]
        self._c = c

        self.setFixedSize(220, 120)
        self.setCursor(Qt.PointingHandCursor)
        self._apply_style(False)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        lbl = QLabel(label)
        lbl.setFont(QFont("Courier New", 16, QFont.Bold))
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(f"color: {c['label']}; letter-spacing: 2px;")
        layout.addWidget(lbl)

    def _apply_style(self, selected: bool):
        c = self._c
        if selected:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {c['selected_bg']};
                    border: 3px solid {c['selected_bd']};
                    border-radius: 12px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {c['default_bg']};
                    border: 2px solid {c['default_bd']};
                    border-radius: 12px;
                }}
            """)

    def set_selected(self, selected: bool):
        self.is_selected = selected
        self._apply_style(selected)

    def mousePressEvent(self, event):
        self.clicked.emit(self.value)


# ─────────────────────────────────────────────────────────────────────────────
# Tela 1: Formulário de registro
# ─────────────────────────────────────────────────────────────────────────────

class FormScreen(QWidget):
    submitted = pyqtSignal(int, str, str)  # id, name, gender

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # Centraliza o card
        center = QHBoxLayout()
        center.addStretch()

        card = QFrame()
        card.setFixedWidth(420)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {PANEL_BG};
                border: 1px solid {BORDER_COLOR};
                border-radius: 16px;
            }}
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(40, 40, 40, 40)
        card_layout.setSpacing(22)

        # Header
        title = QLabel("RoMan Interface")
        title.setFont(QFont("Courier New", 22, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"color: {ACCENT_GREEN}; letter-spacing: 3px; border: none;")

        subtitle = QLabel("Participant Registration")
        subtitle.setFont(QFont("Courier New", 11))
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet(f"color: {TEXT_MUTED}; letter-spacing: 2px; border: none;")

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"background: {BORDER_COLOR}; border: none; max-height: 1px;")

        # Campos
        def make_label(text):
            lbl = QLabel(text)
            lbl.setFont(QFont("Courier New", 10))
            lbl.setStyleSheet(f"color: {TEXT_MUTED}; letter-spacing: 1px; border: none;")
            return lbl

        self.field_id     = QLineEdit()
        self.field_id.setPlaceholderText("e.g. 42")

        self.field_name   = QLineEdit()
        self.field_name.setPlaceholderText("e.g. John Doe")

        self.field_gender = QComboBox()
        self.field_gender.addItems(["Male", "Female", "Non-binary", "Prefer not to say"])

        # Mensagem de erro
        self.error_lbl = QLabel("")
        self.error_lbl.setFont(QFont("Courier New", 10))
        self.error_lbl.setStyleSheet(f"color: {ACCENT_RED}; border: none;")
        self.error_lbl.setAlignment(Qt.AlignCenter)
        self.error_lbl.hide()

        # Botão
        btn_submit = QPushButton("SUBMIT")
        btn_submit.setObjectName("submitBtn")
        btn_submit.setFixedHeight(46)
        btn_submit.clicked.connect(self._on_submit)

        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)
        card_layout.addWidget(sep)
        card_layout.addWidget(make_label("PARTICIPANT ID"))
        card_layout.addWidget(self.field_id)
        card_layout.addWidget(make_label("NAME"))
        card_layout.addWidget(self.field_name)
        card_layout.addWidget(make_label("GENDER"))
        card_layout.addWidget(self.field_gender)
        card_layout.addWidget(self.error_lbl)
        card_layout.addWidget(btn_submit)

        center.addWidget(card)
        center.addStretch()

        outer.addStretch()
        outer.addLayout(center)
        outer.addStretch()

    def _on_submit(self):
        id_text  = self.field_id.text().strip()
        name     = self.field_name.text().strip()
        gender   = self.field_gender.currentText()

        if not id_text:
            self._show_error("ID is required.")
            return
        try:
            pid = int(id_text)
        except ValueError:
            self._show_error("ID must be an integer.")
            return
        if not name:
            self._show_error("Name is required.")
            return

        self.error_lbl.hide()
        self.submitted.emit(pid, name, gender)

    def _show_error(self, msg: str):
        self.error_lbl.setText(f"⚠  {msg}")
        self.error_lbl.show()


# ─────────────────────────────────────────────────────────────────────────────
# Tela 2: Painel do experimento
# ─────────────────────────────────────────────────────────────────────────────

class ExperimentScreen(QWidget):
    send_requested = pyqtSignal(dict)  # emite dados da caixa selecionada

    def __init__(self, parent=None):
        super().__init__(parent)
        self.participant_id = 0
        self.selected_card: ItemCard | None = None
        self.cards: list[ItemCard] = []
        self._build_ui()

    def _build_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(30, 20, 30, 20)
        main.setSpacing(18)

        # ── Header bar ──
        header = QHBoxLayout()

        self.id_badge = QLabel("ID: —")
        self.id_badge.setFont(QFont("Courier New", 14, QFont.Bold))
        self.id_badge.setStyleSheet(f"""
            color: {DARK_BG};
            background: {ACCENT_GREEN};
            border-radius: 8px;
            padding: 6px 18px;
            letter-spacing: 2px;
        """)

        status_dot = QLabel("● LIVE")
        status_dot.setFont(QFont("Courier New", 11))
        status_dot.setStyleSheet(f"color: {ACCENT_GREEN}; letter-spacing: 2px;")

        self.send_btn = QPushButton("SEND COMMAND")
        self.send_btn.setObjectName("sendBtn")
        self.send_btn.setFixedHeight(42)
        self.send_btn.setEnabled(False)
        self.send_btn.clicked.connect(self._on_send)

        header.addWidget(self.id_badge)
        header.addWidget(status_dot)
        header.addStretch()
        header.addWidget(self.send_btn)

        # ── Separador ──
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"background: {BORDER_COLOR}; border: none; max-height: 1px;")

        # ── Grid de caixas ──
        grid_container = QHBoxLayout()
        grid_container.setSpacing(30)

        # Coluna: Justification
        just_col = QVBoxLayout()
        just_col.setSpacing(12)
        just_title = QLabel("JUSTIFICATION")
        just_title.setFont(QFont("Courier New", 13, QFont.Bold))
        just_title.setAlignment(Qt.AlignCenter)
        just_title.setStyleSheet(f"color: {ACCENT_GREEN}; letter-spacing: 3px;")
        just_col.addWidget(just_title)

        just_grid = QGridLayout()
        just_grid.setSpacing(12)
        for i in range(16):
            card = ItemCard(i)
            card.clicked.connect(self._on_card_clicked)
            self.cards.append(card)
            just_grid.addWidget(card, i // 8, i % 8)
        just_col.addLayout(just_grid)


        grid_container.addLayout(just_col)


        # ── Feedback bar ──
        self.feedback_lbl = QLabel("")
        self.feedback_lbl.setFont(QFont("Courier New", 11))
        self.feedback_lbl.setAlignment(Qt.AlignCenter)
        self.feedback_lbl.setStyleSheet(f"color: {TEXT_MUTED}; letter-spacing: 1px;")

        main.addLayout(header)
        main.addWidget(sep)
        main.addStretch()
        main.addLayout(grid_container)
        main.addStretch()
        main.addWidget(self.feedback_lbl)

    def setup(self, participant_id: int):
        self.participant_id = participant_id
        self.id_badge.setText(f"ID: {participant_id:03d}")

    def populate_card(self, box_index: int, item_name: str, difficulty: str,
                    ground_truth: str, classification: str = '', suggestion: bool = False):
        if 0 <= box_index < len(self.cards):
            self.cards[box_index].populate(item_name, difficulty, ground_truth,
                                        classification, suggestion)

    def _on_card_clicked(self, index: int):
        card = self.cards[index]
        if not card.data:
            self.feedback_lbl.setText("⚠  Card not yet populated with data.")
            return

        # Deseleciona anterior
        if self.selected_card and self.selected_card != card:
            self.selected_card.set_selected(False)

        if self.selected_card == card:
            # Toggle off
            card.set_selected(False)
            self.selected_card = None
            self.send_btn.setEnabled(False)
            self.feedback_lbl.setText("")
        else:
            card.set_selected(True)
            self.selected_card = card
            self.send_btn.setEnabled(True)
            name = card.data.get("item_name", "—")
            self.feedback_lbl.setText(f"Selected: {name}  ·  Click SEND COMMAND to confirm")

    def _on_send(self):
        if not self.selected_card or not self.selected_card.data:
            return

        payload = {
            "id": self.participant_id,
            **self.selected_card.data,
        }
        # ── ALTERADO: não marca como sent aqui — espera retorno da ResultScreen
        self.selected_card.set_selected(False)
        self.send_btn.setEnabled(False)
        self.feedback_lbl.setText("")
        self.send_requested.emit(payload)

    # ── ADICIONAR: chamado pela MainWindow ao voltar da ResultScreen
    def mark_last_sent(self):
        """Marca o card que estava pendente como enviado (vermelho)."""
        if self._pending_card:
            self._pending_card.mark_sent()
            self._pending_card = None

    # ── ADICIONAR: guarda referência ao card aguardando confirmação
    def set_pending_card(self, card: 'ItemCard'):
        self._pending_card = card

    _pending_card: 'ItemCard | None' = None

# ─────────────────────────────────────────────────────────────────────────────
# Tela 3: Painel de resultado
# ─────────────────────────────────────────────────────────────────────────────

class ResultScreen(QWidget):
    """
    Exibida após o usuário clicar em SEND COMMAND na ExperimentScreen.

    Contém:
      - Botão TRIGGER (amarelo) → publica /trigger com valor 1
      - Dois cards selecionáveis: RECYCLE (azul) e WASTE (laranja)
      - Botão SEND COMMAND → publica /result com o valor selecionado
        e volta para a ExperimentScreen
    """

    from PyQt5.QtCore import pyqtSignal
    trigger_requested = pyqtSignal()          # → publica /trigger
    result_confirmed  = pyqtSignal(str)       # → publica /result com 'recycle'|'waste'

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected_value: str | None = None
        self._build_ui()

    def _build_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(60, 40, 60, 40)
        main.setSpacing(30)

        # ── Título ──
        title = QLabel("RESULT")
        title.setFont(QFont("Courier New", 20, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"color: {TEXT_PRIMARY}; letter-spacing: 4px;")

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"background: {BORDER_COLOR}; border: none; max-height: 1px;")

        # ── Botão Trigger ──
        self.trigger_btn = QPushButton("TRIGGER")
        self.trigger_btn.setObjectName("triggerBtn")
        self.trigger_btn.setFixedHeight(48)
        self.trigger_btn.clicked.connect(self._on_trigger)

        # ── Cards de escolha ──
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(40)
        cards_layout.setAlignment(Qt.AlignCenter)

        self.card_recycle = ResultOptionCard("recycle", "♻  RECYCLE")
        self.card_waste   = ResultOptionCard("waste",   "🗑  WASTE")

        self.card_recycle.clicked.connect(self._on_option_clicked)
        self.card_waste.clicked.connect(self._on_option_clicked)

        cards_layout.addWidget(self.card_recycle)
        cards_layout.addWidget(self.card_waste)

        # ── Botão Send Command ──
        self.send_btn = QPushButton("SEND COMMAND")
        self.send_btn.setObjectName("resultSendBtn")
        self.send_btn.setFixedHeight(46)
        self.send_btn.setEnabled(False)
        self.send_btn.clicked.connect(self._on_send)

        self.feedback_lbl = QLabel("")
        self.feedback_lbl.setFont(QFont("Courier New", 11))
        self.feedback_lbl.setAlignment(Qt.AlignCenter)
        self.feedback_lbl.setStyleSheet(f"color: {TEXT_MUTED};")

        main.addStretch()
        main.addWidget(title)
        main.addWidget(sep)
        main.addWidget(self.trigger_btn)
        main.addLayout(cards_layout)
        main.addWidget(self.send_btn)
        main.addWidget(self.feedback_lbl)
        main.addStretch()

    def reset(self):
        """Limpa o estado ao entrar na tela."""
        self._selected_value = None
        self.card_recycle.set_selected(False)
        self.card_waste.set_selected(False)
        self.send_btn.setEnabled(False)
        self.feedback_lbl.setText("")

    def _on_trigger(self):
        self.trigger_requested.emit()
        self.feedback_lbl.setText("✓  Trigger sent.")

    def _on_option_clicked(self, value: str):
        self._selected_value = value
        self.card_recycle.set_selected(value == "recycle")
        self.card_waste.set_selected(value == "waste")
        self.send_btn.setEnabled(True)
        self.feedback_lbl.setText(
            f"Selected: {value.upper()}  ·  Click SEND COMMAND to confirm"
        )

    def _on_send(self):
        if not self._selected_value:
            return
        self.result_confirmed.emit(self._selected_value)



# ─────────────────────────────────────────────────────────────────────────────
# Janela principal
# ─────────────────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RoMan Interface")
        self.setMinimumSize(960, 620)
        self.setStyleSheet(STYLE_MAIN)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.form_screen = FormScreen()
        self.exp_screen  = ExperimentScreen()
        self.result_screen = ResultScreen()   # ── ADICIONAR

        self.stack.addWidget(self.form_screen)   # index 0
        self.stack.addWidget(self.exp_screen)    # index 1
        self.stack.addWidget(self.result_screen)  # ── ADICIONAR  index 2

        self.form_screen.submitted.connect(self._on_form_submitted)

        # ── ADICIONAR: conecta ResultScreen ao fluxo
        self.exp_screen.send_requested.connect(self._on_exp_send)
        self.result_screen.result_confirmed.connect(self._on_result_confirmed)

    def _on_form_submitted(self, pid: int, name: str, gender: str):
        """Chamado quando o formulário é submetido."""
        self.exp_screen.setup(pid)
        self.stack.setCurrentIndex(1)
        # O nó ROS publica /id a partir daqui (via callback externo)
        if hasattr(self, '_on_submit_callback'):
            self._on_submit_callback(pid, name, gender)

        # ── ADICIONAR: ao clicar SEND COMMAND na ExperimentScreen
    def _on_exp_send(self, payload: dict):
        # Guarda o card pendente para marcar vermelho ao voltar
        self.exp_screen.set_pending_card(self.exp_screen.selected_card)
        self._pending_payload = payload

        # Publica /sam_data
        if hasattr(self, '_on_send_callback'):
            self._on_send_callback(payload)

        # Vai para ResultScreen
        self.result_screen.reset()
        self.stack.setCurrentIndex(2)

    # ── ADICIONAR: ao confirmar resultado na ResultScreen
    def _on_result_confirmed(self, value: str):
        # Publica /result
        if hasattr(self, '_on_result_callback'):
            self._on_result_callback(value)

        # Marca o card como enviado (vermelho) e volta para ExperimentScreen
        self.exp_screen.mark_last_sent()
        self.stack.setCurrentIndex(1)

    def set_submit_callback(self, cb):
        self._on_submit_callback = cb

    def set_send_callback(self, cb):
        self.exp_screen.send_requested.connect(cb)

        # ── ADICIONAR: callback para /trigger e /result
    def set_trigger_callback(self, cb):
        self.result_screen.trigger_requested.connect(cb)

    def set_result_callback(self, cb):
        self._on_result_callback = cb



# ─────────────────────────────────────────────────────────────────────────────
# Nó ROS2
# ─────────────────────────────────────────────────────────────────────────────

class InterfaceNode(Node):
    def __init__(self, window: MainWindow):
        super().__init__('interface_node')
        self.window = window
        self.get_logger().info('Interface node started.')

        # Publishers
        self.pub_id = self.create_publisher(Int32, '/id', 10)
        self.pub_candidate = self.create_publisher(CandidateData, '/candidate_data', 10)
        self.pub_trigger = self.create_publisher(Int32,  '/trigger', 10)  # ── ADICIONAR
        self.pub_result  = self.create_publisher(String, '/result',  10)  # ── ADICIONAR

        if CUSTOM_MSGS:
            self.pub_sam = self.create_publisher(SamData, '/sam_data', 10)
            self.sub_exp = self.create_subscription(
                ExpData, '/exp_data', self._on_exp_data, 10)
        else:
            self.pub_sam = self.create_publisher(String, '/sam_data', 10)
            self.sub_exp = self.create_subscription(
                String, '/exp_data', self._on_exp_data_fallback, 10)

        # Registra callbacks na janela
        self.window.set_submit_callback(self._on_form_submitted)
        self.window.set_send_callback(self._on_send_command)
        window.set_trigger_callback(self._on_trigger)   # ── ADICIONAR
        window.set_result_callback(self._on_result)     # ── ADICIONAR

    # ── Form submitted ────────────────────────────────────────────────────────

    def _on_form_submitted(self, pid: int, name: str, gender: str):
        msg = Int32()
        msg.data = pid
        self.pub_id.publish(msg)
        self.get_logger().info(f'Published /id: {pid}  name={name}  gender={gender}')
        msg1 = CandidateData()
        msg1.id = pid
        msg1.name = name
        msg1.gender = gender
        self.pub_candidate.publish(msg1)
        self.get_logger().info(f'Published /candidate_data: {pid}  name={name}  gender={gender}')



    # ── Recebe dados do generator ─────────────────────────────────────────────

    def _on_exp_data(self, msg: 'ExpData'):
        """Processa roman_msgs/ExpData e popula a caixa correspondente."""
        self.get_logger().info(
            f'/exp_data → box[{msg.box_index}] item={msg.item_name}'
        )
        # Chama no thread Qt (seguro via QTimer com delay 0)
        self.window.exp_screen.populate_card(
            msg.box_index, msg.item_name, msg.difficulty, msg.ground_truth,
            msg.classification, msg.suggestion
        )

    def _on_exp_data_fallback(self, msg: String):
        """
        Fallback quando roman_msgs não está disponível.
        Espera JSON: {"box_index":0,"item_name":"...","difficulty":"...","ground_truth":"..."}
        """
        import json
        try:
            data = json.loads(msg.data)
            self.window.exp_screen.populate_card(
                data['box_index'], data['item_name'],
                data['difficulty'], data['ground_truth']
            )
        except Exception as e:
            self.get_logger().error(f'Fallback parse error: {e}')

    # ── Send command ──────────────────────────────────────────────────────────

    def _on_send_command(self, payload: dict):
        if CUSTOM_MSGS:
            msg = SamData()
            msg.id           = payload['id']
            msg.item_name    = payload['item_name']
            msg.difficulty   = payload['difficulty']
            msg.ground_truth = payload['ground_truth']
            msg.classification = payload['classification']
            msg.suggestion = payload['suggestion']
            
        else:
            import json
            msg = String()
            msg.data = json.dumps(payload)

        self.pub_sam.publish(msg)
        self.get_logger().info(f'Published /sam_data: {payload}')

    # ── ADICIONAR: publica /trigger com valor 1
    def _on_trigger(self):
        msg = Int32()
        msg.data = 1
        self.pub_trigger.publish(msg)
        self.get_logger().info('Published /trigger: 1')

    # ── ADICIONAR: publica /result com 'recycle' ou 'waste'
    def _on_result(self, value: str):
        msg = String()
        msg.data = value
        self.pub_result.publish(msg)
        self.get_logger().info(f'Published /result: {value}')



# ─────────────────────────────────────────────────────────────────────────────
# Entrypoint
# ─────────────────────────────────────────────────────────────────────────────

def main(args=None):
    rclpy.init(args=args)

    app = QApplication(sys.argv)
    app.setApplicationName("RoMan Interface")

    window = MainWindow()
    window.show()

    node = InterfaceNode(window)

    # Spin ROS em thread separada para não bloquear o Qt
    ros_thread = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    ros_thread.start()

    # Timer Qt para processar callbacks ROS no thread principal quando necessário
    # (os callbacks de UI já são chamados diretamente; o timer garante responsividade)
    ros_timer = QTimer()
    ros_timer.timeout.connect(lambda: None)
    ros_timer.start(50)

    exit_code = app.exec_()

    node.destroy_node()
    rclpy.shutdown()
    sys.exit(exit_code)


if __name__ == '__main__':
    main()