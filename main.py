import sys
from PyQt6.QtWidgets import QApplication
from viewer.gui import MainWindow
from viewer.controller import Controller


def main():
    # Start Qt Application
    app = QApplication(sys.argv)
    screen = app.primaryScreen().availableGeometry()

    # GUI
    window = MainWindow(screen)

    # Start Controller
    Controller(gui=window)
    window.show()
    app.exec()


if __name__ == '__main__':
    main()
