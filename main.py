import sys
from PyQt6.QtWidgets import QApplication
from gui import MainWindow
from controller import Controller


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
