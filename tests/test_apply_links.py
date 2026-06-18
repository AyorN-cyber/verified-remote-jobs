import unittest

from job_pipeline.apply_links import extract_apply_candidates


class ApplyLinkExtractionTests(unittest.TestCase):
    def test_prefers_external_ats_apply_link(self):
        html = """
        <html><body>
          <a href="/remote-jobs/example">Back to job</a>
          <a class="button apply" href="https://jobs.ashbyhq.com/example/abc123">Apply now</a>
          <a href="https://www.linkedin.com/company/example">LinkedIn</a>
        </body></html>
        """
        links = extract_apply_candidates("https://weworkremotely.com/remote-jobs/example", html)
        self.assertEqual(links[0], "https://jobs.ashbyhq.com/example/abc123")

    def test_resolves_relative_apply_link(self):
        html = """
        <html><body>
          <a id="apply-button" href="/remote-jobs/example/apply">Apply for this position</a>
        </body></html>
        """
        links = extract_apply_candidates("https://remoteok.com/remote-jobs/example", html)
        self.assertEqual(links[0], "https://remoteok.com/remote-jobs/example/apply")

    def test_ignores_external_non_apply_links(self):
        html = """
        <html><body>
          <a href="https://www.producthunt.com/products/remotejobs?launch=remote-ok-jobs-api">
            Remote OK Jobs API
          </a>
          <a href="https://jobs.lever.co/example/abc">Apply</a>
        </body></html>
        """
        links = extract_apply_candidates("https://remoteok.com/remote-jobs/example", html)
        self.assertEqual(links, ["https://jobs.lever.co/example/abc"])


if __name__ == "__main__":
    unittest.main()
