import unittest

if __name__ == '__main__':
    # Create a TestLoader instance
    loader = unittest.TestLoader()

    # Discover all tests in the current directory
    suite = loader.discover('.')

    # Create a TestResult instance
    runner = unittest.TextTestRunner()

    # Run the test suite
    result = runner.run(suite)

    # Exit with a non-zero status code if tests failed
    if not result.wasSuccessful():
        exit(1)