# How to Contribute

Want to contribute? Thank you! The project structure is straightforward, and we are thrilled to have your help. 

The `sillon` monorepo is hosted on our GitHub organization page. Everyone should download and install the toolchain by following the [Installation Guide](installation.md) first.

### The Development Workflow

If you want to develop a new feature or fix a bug, follow these steps:

1. **Claim an Issue:** Look at the project backlog on GitHub. If you find a task you want to code, assign it to yourself and move it to the **To Do** status.
2. **Branch Out:** Create a new branch using the feature naming convention: 
   `git checkout -b feature/name_of_the_feature`
3. **Write Code:** Build your feature inside the monorepo!
4. **Test It:** When you are done with your branch, you MUST test it. From the root of the repository, run:
   ```bash
   make test
   ```
5. **Pull Request:** If all tests pass, push your branch and open a Pull Request (PR) on GitHub to merge your code into the `develop` branch. 

> **⚠️ CRITICAL RULE:** We **never** push directly to the `main` branch. All code must go through a PR into `develop` first!
