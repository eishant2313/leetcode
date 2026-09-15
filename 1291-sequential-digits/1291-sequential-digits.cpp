class Solution {
public:
    vector<int> sequentialDigits(int low, int high) {
        vector<int> ans;
        for (int i = 1; i <= 9; i++) {
            int n = 0;
            for (int j = i; j <= 9; j++) {
                n = n * 10 + j;
                if (n >= low && n <= high)
                    ans.push_back(n);
                if (n > high)
                    break;
            }
        }
        sort(ans.begin(), ans.end());
        return ans;
    }
};