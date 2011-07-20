from railroad.viewhosts.views import graphs

class FakeRequest(object):
    def __init__(self, d):
        self.GET = d

def main():
    request = FakeRequest({'host': 'dlcooper01,dljevans01'})

    graphs(request)

if __name__ == '__main__':
    main()
