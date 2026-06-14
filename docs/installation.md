# Installation & Local Development

Setting up the sillon toolchain for local development is incredibly fast thanks to our monorepo structure.

### Prerequisites
* Git
* Python >= 3.13

### Setup Instructions

1. **Clone the repository:**
   ```bash
   git clone https://github.com/ThesillonProject/sillon.git
   cd sillon
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```

3. **Install the monorepo via Makefile:**
   ```bash
   make install
   ```

That's it! You can now start coding. 

Because we use an editable install, `sillonCLI` will be immediately accessible in your terminal. You can test it by sillon typing:
```bash
sillon --help
```

### Running Tests
To ensure your local environment is working perfectly, run the test suite:
```bash
make test
```
